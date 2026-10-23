# ======================================================================= #
#  通用组件服务基类（方案 A）
#
#  所有 install_method 的实现都必须提供：
#    install() / remove() / update() / status()  ✓
#  并在**修改任何已有文件前**登记事务（tx_modify）✓
#
#  事务：直接用仓库内 kiauh/core/… 没有事务模块 ✗
#  → 本包自带轻量事务（manifest + 备份目录）✓
#     为什么不用 Woloong-OS 的 transaction.sh ✗：仓库要**自闭环** ✓
# ======================================================================= #
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import List, Optional

HOME = Path(os.environ.get("WO_HOME") or Path.home())   # 可用 WO_HOME 注入（测试/多实例 ✓）
# ★ OI-016（2026-10-23 上机实测）：默认写到 ~/.config/woloong/state ✗
#   而安装器用 /opt/woloong/state ✗ -> 两套台账互不相认 ✗
#   （TUI 卸载后真实台账不变；管理菜单也读不到已装组件 ✗）
#   改为：默认跟随 WO_ROOT/state（与安装器一致 ✓），无 WO_ROOT 时才回落 home ✓
_WO_ROOT = Path(os.environ.get("WO_ROOT", "/opt/woloong"))
STATE = Path(
    os.environ.get(
        "WO_STATE_DIR",
        str(_WO_ROOT / "state") if _WO_ROOT.exists() else str(HOME / ".config" / "woloong" / "state"),
    )
)


class ComponentError(RuntimeError):
    pass


def expand(p: Optional[str]) -> Optional[Path]:
    if not p:
        return None
    s = str(p).strip()
    if s.startswith("~"):
        return HOME / s[2:] if s.startswith("~/") else HOME
    return Path(s)


def run(cmd: List[str], cwd: Optional[Path] = None, check: bool = True) -> int:
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    if check and proc.returncode != 0:
        raise ComponentError("命令失败(%d)：%s" % (proc.returncode, " ".join(cmd)))
    return proc.returncode


def rmtree(path: Path) -> None:
    """跨平台递归删除：先解除只读（Windows 的 .git/objects 是只读 ✗），再删。"""
    p = Path(path)
    if not p.exists():
        return
    if p.is_file() or p.is_symlink():
        try:
            os.chmod(p, stat.S_IWRITE)
        except OSError:
            pass
        p.unlink(missing_ok=True)
        return
    for root, dirs, files in os.walk(p, topdown=False):
        for name in files:
            fp = Path(root) / name
            try:
                os.chmod(fp, stat.S_IWRITE)
            except OSError:
                pass
            try:
                fp.unlink()
            except OSError:
                pass
        for name in dirs:
            dp = Path(root) / name
            try:
                dp.rmdir()
            except OSError:
                pass
    try:
        p.rmdir()
    except OSError:
        shutil.rmtree(p, ignore_errors=True)

class Transaction:
    """极简事务：记录将改动的文件并备份，失败可回滚 ✓。"""

    def __init__(self, tag: str) -> None:
        self.dir = STATE / "tx" / tag
        self.bak = self.dir / "bak"
        self.log = self.dir / "tx.log"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.bak.mkdir(parents=True, exist_ok=True)
        self.log.write_text("", encoding="utf-8")

    def _rec(self, op: str, path: Path, extra: str = "") -> None:
        with self.log.open("a", encoding="utf-8") as fh:
            fh.write("%s\t%s\t%s\n" % (op, path, extra))

    def add(self, path: Path) -> None:
        self._rec("ADD", path)

    def modify(self, path: Path) -> None:
        if not path.exists():
            self._rec("ADD", path)
            return
        # 用哈希做备份名：Windows 下 \\ 与盘符会让路径非法 ✗（实测 WinError 32）
        dst = self.bak / (hashlib.sha256(str(path).encode("utf-8")).hexdigest() + ".bak")
        if path.is_dir():
            # ★ 目录必须用 copytree ✗ 用 copy2 会 Permission denied ✗（实测）
            try:
                shutil.copytree(path, dst)
                self._rec("MOD", path, str(dst) + "|dir")
            except (OSError, shutil.Error):
                # 备份失败 -> 记为 ADD（回滚时删除 ✓），并明确告警 ✗ 不静默
                print("  [WARN] 目录备份失败，按新增处理（回滚将删除）：%s" % path)
                self._rec("ADD", path)
            return
        shutil.copy2(path, dst)
        self._rec("MOD", path, str(dst))

    def rollback(self) -> None:
        for line in reversed(self.log.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            parts = line.split("\t")
            op, path = parts[0], Path(parts[1])
            if op == "ADD":
                if path.is_dir():
                    rmtree(path)
                elif path.exists():
                    path.unlink(missing_ok=True)
            elif op == "MOD" and len(parts) > 2:
                src = parts[2].split("|")[0]
                isdir = parts[2].endswith("|dir")
                if not Path(src).exists():
                    continue
                if isdir:
                    if path.is_dir():
                        rmtree(path)
                    shutil.copytree(src, path)
                else:
                    shutil.copy2(src, path)

    def commit(self) -> None:
        shutil.rmtree(self.bak, ignore_errors=True)


class ComponentService:
    """单个组件的装/卸/更新/状态。子类实现 _install/_remove/_update。"""

    method = "base"

    def __init__(self, spec: dict) -> None:
        self.spec = spec
        self.id = spec["id"]

    # ---- 对外接口 ----
    def install(self, tx: Transaction) -> None:
        self._install(tx)

    def remove(self, tx: Transaction) -> None:
        self._remove(tx)

    def update(self, tx: Transaction) -> None:
        self._update(tx)

    def status(self) -> dict:
        tgt = expand(self.spec.get("target_path"))
        return {
            "id": self.id,
            "method": self.method,
            "target": str(tgt) if tgt else None,
            "installed": bool(tgt and tgt.exists()),
        }

    # ---- 子类实现 ----
    def _install(self, tx: Transaction) -> None:
        raise ComponentError("%s: 未实现 install" % self.id)

    def _remove(self, tx: Transaction) -> None:
        raise ComponentError("%s: 未实现 remove" % self.id)

    def _update(self, tx: Transaction) -> None:
        raise ComponentError("%s: 未实现 update" % self.id)

    # ---- 便捷 ----
    def repo_url(self) -> str:
        """repo 支持：GitHub 短名 / 完整 URL / 本地路径（测试用）。"""
        r = self.spec.get("repo")
        if not r:
            raise ComponentError("%s: 缺 repo" % self.id)
        s = str(r).strip()
        if s.startswith(("http://", "https://", "git@", "ssh://", "file://", "/", "~", "./", "../")):
            return s
        if Path(s).exists():
            return s
        return "https://github.com/%s.git" % s.rstrip("/")
