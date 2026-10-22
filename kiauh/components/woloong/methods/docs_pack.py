# ======================================================================= #
#  docs_pack（自实现）：离线文档拷贝 ✓
#
#  · clone -> 按 items 拷到 target_path ✓
#  · **default_state = installed 但非必需** ✓（文档缺失不影响打印 ✓）
#  · remove：整目录删除 ✓（文档是纯增量，无配置副作用 ✓）
# ======================================================================= #
from __future__ import annotations

import shutil
from pathlib import Path

from .base import HOME, ComponentError, ComponentService, Transaction, expand, rmtree, run


class DocsPackService(ComponentService):
    method = "docs_pack"

    def target(self) -> Path:
        t = expand(self.spec.get("target_path"))
        if t and str(t).startswith("/opt/"):
            # 系统目录可能不可写 ✗ -> 回落到用户目录 ✓（保持可用性 ✓）
            try:
                t.parent.mkdir(parents=True, exist_ok=True)
            except OSError:
                t = HOME / "woloong-docs" / self.id
        return t or (HOME / "woloong-docs" / self.id)

    def staging(self) -> Path:
        return HOME / (".woloong-src-" + self.id)

    def status(self) -> dict:
        st = super().status()
        tgt = self.target()
        st["target"] = str(tgt)
        st["deployed"] = tgt.exists() and any(tgt.iterdir()) if tgt.exists() else False
        return st

    def _sync(self, tx: Transaction) -> None:
        stage = self.staging()
        if not (stage / ".git").is_dir():
            rmtree(stage)
            run(["git", "clone", "--depth", "1", self.repo_url(), str(stage)])
            tx.add(stage)
        else:
            run(["git", "-C", str(stage), "pull", "--ff-only"], check=False)
        tgt = self.target()
        tx.modify(tgt)
        if tgt.exists():
            rmtree(tgt)
        tgt.mkdir(parents=True, exist_ok=True)
        items = self.spec.get("items") or []
        if not items:
            raise ComponentError("%s: 目录缺 items" % self.id)
        for it in items:
            src = stage / it["src"]
            if not src.exists():
                continue   # 文档可缺项 ✓（非致命 ✓）
            dst = tgt / it["dest"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)

    def _install(self, tx: Transaction) -> None:
        self._sync(tx)

    def _remove(self, tx: Transaction) -> None:
        tgt = self.target()
        if tgt.exists():
            tx.add(tgt)
            rmtree(tgt)
        stage = self.staging()
        if stage.exists():
            tx.add(stage)
            rmtree(stage)

    def _update(self, tx: Transaction) -> None:
        self._sync(tx)
