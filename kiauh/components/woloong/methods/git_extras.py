# ======================================================================= #
#  git_extras：把上游仓库里的模块拷进 Klipper 的 klippy/extras/  ✓
#
#  这是**方案 A 的样板实现**（先做 1 个，验证通过再批量 ✓）
#  对应组件：shaketune / z_calibration / led_effect / tmc_autotune / auto_speed
#
#  install : clone 到 ~/<repo> -> **软链** items 进 klippy/extras -> 写 cfg -> include
#  remove  : 删软链 -> 删 cfg -> 去 include -> 删 clone -> 清 git exclude
#  update  : git pull -> 重建软链
#
#  ★ 整合决议 v1.0（R3）：**必须 symlink，不能 copy** ✗
#    copy 会让「网页端更新成功但功能不变」→ 假更新 ✗
#    软链还会让 Klipper 仓库出现未跟踪文件 → 必须写入 .git/info/exclude ✓
#    （与 Woloong-OS 的 install/lib/methods.sh 行为一致 ✓）
# ======================================================================= #
from __future__ import annotations

import shutil
from pathlib import Path
from typing import List

from .base import (
    HOME,
    ComponentError,
    ComponentService,
    Transaction,
    expand,
    rmtree,
    run,
)


class GitExtrasService(ComponentService):
    method = "git_extras"

    # ---------- 路径 ----------
    def clone_dir(self) -> Path:
        # ★ P91（2026-10-22 真机 ✗）：git_extras 的 target_path 是 **klippy/extras/** ✗
        #   以前直接拿它当 clone 目录 ✗ -> 会往 klipper 的 extras 里 clone 仓库 ✗✗
        #   Windows 门禁因覆盖了 target_path 才没暴露 ✗
        #   修：clone 到独立暂存目录 ✓（extras 只作为**拷贝目标** ✓）
        override = expand(self.spec.get("src_dir"))
        if override is not None:
            return override
        repo = (self.spec.get("repo") or "").rstrip("/").split("/")[-1]
        name = repo[:-4] if repo.endswith(".git") else repo
        return HOME / (name or self.id)

    def extras_dir(self) -> Path:
        return HOME / "klipper" / "klippy" / "extras"

    def config_dir(self) -> Path:
        return HOME / "printer_data" / "config"

    # ---------- 状态 ----------
    def status(self) -> dict:
        st = super().status()
        st["clone"] = self.clone_dir().exists()
        st["files"] = [str(self.extras_dir() / it["dest"]) for it in (self.spec.get("items") or [])]
        st["deployed"] = all(Path(p).exists() for p in st["files"]) if st["files"] else False
        return st

    # ---------- install ----------
    def _install(self, tx: Transaction) -> None:
        repo = self.repo_url()
        clone = self.clone_dir()
        if not clone.exists():
            clone.parent.mkdir(parents=True, exist_ok=True)
            tx.add(clone)
            run(["git", "clone", "--depth", "1", repo, str(clone)])
        else:
            run(["git", "-C", str(clone), "pull", "--ff-only"], check=False)
        self._deploy(tx, clone)

    def _deploy(self, tx: Transaction, clone: Path) -> None:
        extras = self.extras_dir()
        if not extras.is_dir():
            raise ComponentError("%s: 找不到 Klipper extras 目录（%s）" % (self.id, extras))
        items = self.spec.get("items") or []
        if not items:
            raise ComponentError("%s: 目录缺 items（无处拷贝）" % self.id)
        for it in items:
            src = clone / it["src"]
            dst = extras / it["dest"]
            if not src.exists():
                raise ComponentError("%s: 仓库内缺 %s" % (self.id, it["src"]))
            tx.modify(dst)
            if dst.exists() or dst.is_symlink():
                dst.unlink() if (dst.is_file() or dst.is_symlink()) else rmtree(dst)
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                dst.symlink_to(src, target_is_directory=src.is_dir())
            except (OSError, NotImplementedError):
                # Windows 无符号链接权限时退化为 copy（仅测试环境；Linux 走软链 ✓）
                print("  [WARN] 无法创建符号链接，退化为拷贝（仅限无权限环境）：%s" % dst)
                shutil.copytree(src, dst) if src.is_dir() else shutil.copy2(src, dst)
        self._git_exclude(tx, [it["dest"] for it in items], add=True)
        self._write_config(tx)

    def _write_config(self, tx: Transaction) -> None:
        cfg_name = self.spec.get("config_file")
        if not cfg_name:
            return
        cfgdir = self.config_dir()
        cfgdir.mkdir(parents=True, exist_ok=True)
        cfg = cfgdir / cfg_name
        tx.modify(cfg)
        if not cfg.exists():
            cfg.write_text(
                "# %s（Woloong 由 kiauh 管理）\n# 该模块无必需配置项；按需在此添加。\n" % self.id,
                encoding="utf-8",
            )
        pc = cfgdir / "printer.cfg"
        if not pc.exists():
            return
        line = "[include %s]" % cfg_name
        text = pc.read_text(encoding="utf-8", errors="replace")
        if line in text.splitlines():
            return
        tx.modify(pc)
        with pc.open("a", encoding="utf-8") as fh:
            fh.write("\n%s\n" % line)

    def _git_exclude(self, tx: Transaction, names: List[str], add: bool) -> None:
        """把软链路径写进 Klipper 仓库的 .git/info/exclude ✓

        原因：软链进 klippy/extras 的 .py 对 Klipper 仓库是**未跟踪文件** ✗
          -> Moonraker 把 Klipper 判成 dirty ✗ -> update_manager 不可用 ✗
        """
        gi = HOME / "klipper" / ".git" / "info" / "exclude"
        if not gi.exists():
            return
        rels = ["klippy/extras/%s" % n for n in names]
        lines = gi.read_text(encoding="utf-8", errors="replace").splitlines()
        changed = False
        if add:
            for rel in rels:
                if rel not in lines:
                    lines.append(rel)
                    changed = True
        else:
            kept = [ln for ln in lines if ln not in rels]
            if len(kept) != len(lines):
                lines = kept
                changed = True
        if changed:
            tx.modify(gi)
            gi.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---------- remove ----------
    def _remove(self, tx: Transaction) -> None:
        extras = self.extras_dir()
        for it in self.spec.get("items") or []:
            dst = extras / it["dest"]
            if not dst.exists():
                continue
            tx.add(dst)
            if dst.is_dir():
                rmtree(dst)
            else:
                dst.unlink()
        cfg_name = self.spec.get("config_file")
        if cfg_name:
            cfg = self.config_dir() / cfg_name
            if cfg.exists():
                tx.add(cfg)
                cfg.unlink()
            pc = self.config_dir() / "printer.cfg"
            if pc.exists():
                line = "[include %s]" % cfg_name
                lines = pc.read_text(encoding="utf-8", errors="replace").splitlines(True)
                idx = next((i for i, ln in enumerate(lines) if ln.strip() == line), -1)
                if idx >= 0:
                    kept = lines[:idx] + lines[idx + 1:]
                    # 安装时写的是 "\n[include X]\n"（含前导空行）-> 卸载时一并撤掉 ✓
                    if idx - 1 >= 0 and kept[idx - 1:idx] and kept[idx - 1].strip() == "":
                        kept = kept[:idx - 1] + kept[idx:]
                    tx.modify(pc)
                    pc.write_text("".join(kept), encoding="utf-8")
        self._git_exclude(tx, [it["dest"] for it in (self.spec.get("items") or [])], add=False)
        clone = self.clone_dir()
        if clone.exists():
            tx.add(clone)
            rmtree(clone)

    # ---------- update ----------
    def _update(self, tx: Transaction) -> None:
        clone = self.clone_dir()
        if not clone.exists():
            raise ComponentError("%s: 未安装（无 %s）" % (self.id, clone))
        run(["git", "-C", str(clone), "pull", "--ff-only"])
        self._deploy(tx, clone)
