# ======================================================================= #
#  git_service（自实现分支）：**纯 clone 型** ✓
#    只处理「上游没有对应实现、且没有 systemd 单元」的组件（如 katapult）✓
#    有 systemd 单元的组件（如 spoolman）走 venv/systemd 阶段 ✗（暂缓）
#
#  与 delegate.py 的分工：
#    · 上游已有实现（klipper/moonraker/klipperscreen/crowsnest）-> delegate ✓
#    · 上游没有、且只需 clone                                     -> 本类 ✓
# ======================================================================= #
from __future__ import annotations

from pathlib import Path

from .base import HOME, ComponentError, ComponentService, Transaction, expand, rmtree, run


class GitService(ComponentService):
    method = "git_service"

    def target(self) -> Path:
        return expand(self.spec.get("target_path")) or (HOME / self.id)

    def status(self) -> dict:
        st = super().status()
        tgt = self.target()
        st["git"] = (tgt / ".git").is_dir()
        return st

    def _install(self, tx: Transaction) -> None:
        if self.spec.get("service"):
            raise ComponentError(
                "%s: 有 systemd 单元，需走 venv/systemd 阶段（尚未迁移）" % self.id
            )
        tgt = self.target()
        repo = self.repo_url()
        if (tgt / ".git").is_dir():
            run(["git", "-C", str(tgt), "pull", "--ff-only"], check=False)
            return
        if tgt.exists() and any(tgt.iterdir()):
            raise ComponentError("%s: 目标已存在且非空（%s）" % (self.id, tgt))
        tgt.parent.mkdir(parents=True, exist_ok=True)
        tx.add(tgt)
        run(["git", "clone", "--depth", "1", repo, str(tgt)])

    def _remove(self, tx: Transaction) -> None:
        tgt = self.target()
        if not tgt.exists():
            return
        tx.add(tgt)
        rmtree(tgt)

    def _update(self, tx: Transaction) -> None:
        tgt = self.target()
        if not (tgt / ".git").is_dir():
            raise ComponentError("%s: 未安装（无 %s/.git）" % (self.id, tgt))
        run(["git", "-C", str(tgt), "pull", "--ff-only"])
