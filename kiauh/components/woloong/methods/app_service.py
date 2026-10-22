# ======================================================================= #
#  app_service：带「脚本/服务」形状的组件 ✓
#
#  覆盖两个 install_method：
#    script_install                        —— 7 个（klipper_backup/cartographer_firmware/telegram_bot/
#                                             kiauh/timelapse/afc/afc_klipperscreen）
#    git_service（有 service 且非委托）    —— spoolman
#
#  统一流程：
#    clone -> 按 items 拷进 target_path -> [可选] 建 venv -> [可选] 写 systemd 单元
#
#  ★ 单元文件写到 STATE/systemd/<svc>.service ✓（**不直接写 /etc/systemd** ✗）
#    理由与 nginx 一致：仓库不假设 root ✓，由 OS 层安装/启用 ✓
#
#  ★ venv 可用 WO_SKIP_VENV=1 跳过 ✓（门禁/离线测试用）
# ======================================================================= #
from __future__ import annotations

import os
import shutil
from pathlib import Path

from .base import HOME, STATE, ComponentError, ComponentService, Transaction, expand, rmtree, run


class AppService(ComponentService):
    method = "script_install"

    # ---------- 路径 ----------
    def target(self) -> Path:
        return expand(self.spec.get("target_path")) or (HOME / ("woloong-" + self.id))

    def staging(self) -> Path:
        return HOME / (".woloong-src-" + self.id)

    def venv(self):
        return expand(self.spec.get("venv"))

    def unit(self):
        svc = self.spec.get("service")
        if not svc:
            return None
        return Path(os.environ.get("WO_SYSTEMD_DIR") or (STATE / "systemd")) / (svc + ".service")

    # ---------- 状态 ----------
    def status(self) -> dict:
        st = super().status()
        tgt = self.target()
        st["target"] = str(tgt)
        st["deployed"] = tgt.exists() and any(tgt.iterdir()) if tgt.exists() else False
        u = self.unit()
        st["unit"] = str(u) if u and u.exists() else None
        return st

    # ---------- 同步 ----------
    def _sync(self, tx: Transaction) -> None:
        stage = self.staging()
        if not (stage / ".git").is_dir():
            rmtree(stage)
            run(["git", "clone", "--depth", "1", self.repo_url(), str(stage)])
            tx.add(stage)
        else:
            run(["git", "-C", str(stage), "pull", "--ff-only"], check=False)
        tgt = self.target()
        tgt.mkdir(parents=True, exist_ok=True)
        items = self.spec.get("items") or []
        if not items:
            raise ComponentError("%s: 目录缺 items" % self.id)
        for it in items:
            src = stage / it["src"]
            if not src.exists():
                raise ComponentError("%s: 仓库内缺 %s" % (self.id, it["src"]))
            dst = tgt / it["dest"]
            tx.modify(dst)
            excludes = it.get("exclude") or []
            if src.is_dir():
                if dst.exists() and it["dest"] not in (".", ""):
                    rmtree(dst)
                ignore = shutil.ignore_patterns(*excludes) if excludes else None
                try:
                    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=ignore)
                except (PermissionError, shutil.Error, OSError) as exc:
                    # 兜底：逐文件拷贝（跳过 .git 与不可读项 ✓），保证安装不因个别文件失败 ✗
                    print("  [WARN] %s: copytree 部分失败（%s），改逐文件拷贝" % (self.id, exc))
                    _copy_loose(src, dst, excludes)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

    # ---------- venv ----------
    def _make_venv(self, tx: Transaction) -> None:
        venv = self.venv()
        if not venv:
            return
        if os.environ.get("WO_SKIP_VENV") == "1":
            print("  [WARN] %s: WO_SKIP_VENV=1，跳过 venv 创建" % self.id)
            return
        if not (venv / "bin" / "python").exists():
            tx.add(venv)
            run(["python3", "-m", "venv", str(venv)])
        req = self.target() / "requirements.txt"
        if req.exists():
            wh = Path(os.environ.get("WO_WHEELHOUSE") or "")
            pip = venv / "bin" / "pip"
            cmd = [str(pip), "install", "-q"]
            if str(wh) and wh.is_dir():
                cmd += ["--no-index", "--find-links", str(wh)]
            cmd += ["-r", str(req)]
            run(cmd, check=False)

    # ---------- systemd 单元 ----------
    def _write_unit(self, tx: Transaction) -> None:
        u = self.unit()
        if not u:
            return
        svc = self.spec.get("service")
        exec_line = self.spec.get("exec")
        if not exec_line:
            raise ComponentError("%s: 有 service 但目录缺 exec（无法生成单元）" % self.id)
        u.parent.mkdir(parents=True, exist_ok=True)
        tx.modify(u)
        u.write_text(
            "\n".join(
                [
                    "[Unit]",
                    "Description=Woloong %s" % self.id,
                    "After=network-online.target moonraker.service",
                    "Wants=network-online.target",
                    "",
                    "[Service]",
                    "Type=simple",
                    "User=%s" % os.environ.get("WO_USER", "pi"),
                    "WorkingDirectory=%s" % self.target(),
                    "ExecStart=%s" % exec_line,
                    "Restart=always",
                    "RestartSec=5",
                    "",
                    "[Install]",
                    "WantedBy=multi-user.target",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    # ---------- 对外 ----------
    def _install(self, tx: Transaction) -> None:
        self._sync(tx)
        self._make_venv(tx)
        self._write_unit(tx)

    def _remove(self, tx: Transaction) -> None:
        tgt = self.target()
        if tgt.exists():
            tx.add(tgt)
            rmtree(tgt)
        stage = self.staging()
        if stage.exists():
            tx.add(stage)
            rmtree(stage)
        u = self.unit()
        if u and u.exists():
            tx.add(u)
            u.unlink()
        venv = self.venv()
        if venv and venv.exists() and self.spec.get("method") == "script_install":
            tx.add(venv)
            rmtree(venv)

    def _update(self, tx: Transaction) -> None:
        self._sync(tx)
        self._write_unit(tx)


def _copy_loose(src: Path, dst: Path, excludes) -> None:
    """逐文件拷贝兜底：跳过 exclude 与 .git；单文件失败只跳过 ✓。"""
    skip = set(excludes or []) | {".git"}
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in skip]
        rel = Path(root).relative_to(src)
        out = dst / rel
        out.mkdir(parents=True, exist_ok=True)
        for name in files:
            if name in skip:
                continue
            try:
                shutil.copy2(Path(root) / name, out / name)
            except OSError:
                pass