# ======================================================================= #
#  web_static（自实现）：前端静态站（Mainsail / Fluidd）✓
#
#  来源优先级（离线优先 ✓）：
#    ① WO_CACHE_FILES/<id>/            离线目录（整包解压好的）✓
#    ② WO_CACHE_FILES/<id>.zip         离线 zip ✓
#    ③ release 资产（GitHub）          联网下载 ✓ + **sha256 校验**（若目录声明）
#
#  nginx：本服务**不碰 /etc/nginx** ✗（那是 OS 层 ✗）
#    · web_path 为 '/'（根站）-> 不写片段 ✓（由 OS 的 default server 承担 ✓）
#    · 其它 -> 写 location 片段到 STATE/nginx/<id>.conf ✓，OS 层 include ✓
#    这样避免「重复 server」✗（实测 nginx -t 报 conflicting server name ✗）
# ======================================================================= #
from __future__ import annotations

import hashlib
import os
import shutil
import urllib.request
import zipfile
from pathlib import Path

from .base import HOME, STATE, ComponentError, ComponentService, Transaction, expand, rmtree, run


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class WebStaticService(ComponentService):
    method = "web_static"

    def target(self) -> Path:
        return expand(self.spec.get("target_path")) or (HOME / ("woloong-" + self.id))

    def cache_files(self) -> Path:
        return expand(os.environ.get("WO_CACHE_FILES") or "/opt/woloong/cache/files")

    def snippet_dir(self) -> Path:
        return Path(os.environ.get("WO_NGINX_DIR") or (STATE / "nginx"))

    def snippet(self) -> Path:
        return self.snippet_dir() / (self.id + ".conf")

    def web_path(self) -> str:
        wp = self.spec.get("web_path") or ""
        return wp if wp else ""

    # ---- 状态 ----
    def status(self) -> dict:
        st = super().status()
        tgt = self.target()
        st["index"] = (tgt / "index.html").exists()
        st["deployed"] = st["index"]
        st["snippet"] = str(self.snippet()) if self.snippet().exists() else None
        return st

    # ---- 取源 ----
    def _materialize(self, tx: Transaction) -> Path:
        """返回一个「解压好的目录」路径（可能就在 cache 里，不需要复制 ✓）。"""
        root = self.cache_files()
        local_dir = root / self.id
        if (local_dir / "index.html").exists():
            return local_dir
        local_zip = root / (self.id + ".zip")
        tmpdir = Path(os.environ.get("WO_TMP", "/tmp")) / ("woloong-web-" + self.id)
        if local_zip.exists():
            return self._unzip(local_zip, tmpdir, tx)
        rel = self.spec.get("release") or {}
        tag, asset = rel.get("tag"), rel.get("asset")
        if not (tag and asset):
            raise ComponentError(
                "%s: 无离线资产（%s）且目录未声明 release（tag/asset）" % (self.id, local_dir)
            )
        url = "https://github.com/%s/releases/download/%s/%s" % (self.spec["repo"], tag, asset)
        tmpdir.mkdir(parents=True, exist_ok=True)
        zpath = tmpdir / asset
        rmtree(zpath)
        urllib.request.urlretrieve(url, zpath)
        want = self.spec.get("sha256")
        if want:
            got = _sha256(zpath)
            if got != want:
                rmtree(zpath)
                raise ComponentError("%s: sha256 不符（want %s / got %s）" % (self.id, want[:12], got[:12]))
        else:
            print("  [WARN] %s: 目录未声明 sha256，无法校验完整性" % self.id)
        return self._unzip(zpath, tmpdir, tx)

    def _unzip(self, zpath: Path, tmpdir: Path, tx: Transaction) -> Path:
        out = tmpdir / "unpacked"
        rmtree(out)
        out.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zpath) as zf:
            zf.extractall(out)
        # 若 zip 只有单层目录（常见 ✓），下钻一层
        entries = [p for p in out.iterdir()]
        if len(entries) == 1 and entries[0].is_dir() and not (out / "index.html").exists():
            return entries[0]
        return out

    # ---- 装 ----
    def _install(self, tx: Transaction) -> None:
        src = self._materialize(tx)
        tgt = self.target()
        if not (src / "index.html").exists():
            raise ComponentError("%s: 资产里没有 index.html（%s）" % (self.id, src))
        tx.modify(tgt)
        if tgt.exists():
            rmtree(tgt)
        tgt.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, tgt)
        self._write_snippet(tx)

    def _write_snippet(self, tx: Transaction) -> None:
        wp = self.web_path()
        if wp in ("", "/"):
            return   # 根站由 OS 的 default server 承担 ✓（避免重复 server ✗）
        snip = self.snippet()
        snip.parent.mkdir(parents=True, exist_ok=True)
        tx.modify(snip)
        body = [
            "# Woloong 由 kiauh 生成：%s 的 location 片段" % self.id,
            "# 由 OS 层的 server 块 include；不要单独建 server（会冲突 ✗）",
            "location %s {" % wp,
            "    alias %s/;" % self.target(),
            "    try_files $uri $uri/ %sindex.html;" % wp,
            "}",
            "",
        ]
        snip.write_text("\n".join(body), encoding="utf-8")

    # ---- 卸 ----
    def _remove(self, tx: Transaction) -> None:
        tgt = self.target()
        if tgt.exists():
            tx.add(tgt)
            rmtree(tgt)
        snip = self.snippet()
        if snip.exists():
            tx.add(snip)
            snip.unlink()

    # ---- 更新 ----
    def _update(self, tx: Transaction) -> None:
        self._install(tx)
