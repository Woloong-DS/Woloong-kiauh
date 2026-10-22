# ======================================================================= #
#  config_pack（自实现）：把仓库里的配置目录/文件装进 printer_data/config ✓
#
#  与 git_extras 的区别：
#    · 不碰 klippy/extras ✓
#    · 目标在 config 目录下（items.dest 相对 config dir ✓）
#    · include 行**默认注释** ✓（KAMP 必须保持注释 ✗ 不许自动启用 ✗ —— P50）
# ======================================================================= #
from __future__ import annotations

from pathlib import Path

from .base import HOME, ComponentError, ComponentService, Transaction, expand, rmtree, run


class ConfigPackService(ComponentService):
    method = "config_pack"

    def config_dir(self) -> Path:
        return HOME / "printer_data" / "config"

    def staging(self) -> Path:
        return HOME / (".woloong-src-" + self.id)

    def dests(self):
        out = []
        for it in self.spec.get("items") or []:
            out.append(self.config_dir() / it["dest"])
        return out

    def status(self) -> dict:
        st = super().status()
        st["files"] = [str(p) for p in self.dests()]
        st["deployed"] = bool(st["files"]) and all(Path(p).exists() for p in st["files"])
        return st

    def _install(self, tx: Transaction) -> None:
        cfgdir = self.config_dir()
        cfgdir.mkdir(parents=True, exist_ok=True)
        stage = self.staging()
        if not (stage / ".git").is_dir():
            rmtree(stage)
            run(["git", "clone", "--depth", "1", self.repo_url(), str(stage)])
            tx.add(stage)
        else:
            run(["git", "-C", str(stage), "pull", "--ff-only"], check=False)
        items = self.spec.get("items") or []
        if not items:
            raise ComponentError("%s: 目录缺 items" % self.id)
        for it in items:
            src = stage / it["src"]
            dst = cfgdir / it["dest"]
            if not src.exists():
                raise ComponentError("%s: 仓库内缺 %s" % (self.id, it["src"]))
            tx.modify(dst)
            if src.is_dir():
                if dst.exists():
                    rmtree(dst)
                dst.parent.mkdir(parents=True, exist_ok=True)
                _copy_tree(src, dst)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(src.read_bytes())
        self._write_include(tx)

    def _write_include(self, tx: Transaction) -> None:
        line = self.spec.get("include_line")
        if not line:
            return
        pc = self.config_dir() / "printer.cfg"
        if not pc.exists():
            return
        text = pc.read_text(encoding="utf-8", errors="replace")
        if line in text.splitlines():
            return
        tx.modify(pc)
        with pc.open("a", encoding="utf-8") as fh:
            fh.write("\n%s\n" % line)

    def _remove(self, tx: Transaction) -> None:
        cfgdir = self.config_dir()
        for it in self.spec.get("items") or []:
            dst = cfgdir / it["dest"]
            if dst.exists():
                tx.add(dst)
                rmtree(dst)
        line = self.spec.get("include_line")
        if line:
            pc = cfgdir / "printer.cfg"
            if pc.exists():
                lines = pc.read_text(encoding="utf-8", errors="replace").splitlines(True)
                idx = next((i for i, ln in enumerate(lines) if ln.strip() == line.strip()), -1)
                if idx >= 0:
                    kept = lines[:idx] + lines[idx + 1:]
                    if idx - 1 >= 0 and kept[idx - 1:idx] and kept[idx - 1].strip() == "":
                        kept = kept[:idx - 1] + kept[idx:]
                    tx.modify(pc)
                    pc.write_text("".join(kept), encoding="utf-8")
        stage = self.staging()
        if stage.exists():
            tx.add(stage)
            rmtree(stage)

    def _update(self, tx: Transaction) -> None:
        stage = self.staging()
        if not (stage / ".git").is_dir():
            raise ComponentError("%s: 未安装（无 %s）" % (self.id, stage))
        run(["git", "-C", str(stage), "pull", "--ff-only"])
        cfgdir = self.config_dir()
        for it in self.spec.get("items") or []:
            src = stage / it["src"]
            dst = cfgdir / it["dest"]
            if not src.exists():
                raise ComponentError("%s: 仓库内缺 %s" % (self.id, it["src"]))
            tx.modify(dst)
            if dst.exists():
                rmtree(dst)
            if src.is_dir():
                _copy_tree(src, dst)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(src.read_bytes())


def _copy_tree(src: Path, dst: Path) -> None:
    """复制目录（不依赖 shutil.copytree 的 exist_ok 行为 ✓）。"""
    import shutil

    shutil.copytree(src, dst)
