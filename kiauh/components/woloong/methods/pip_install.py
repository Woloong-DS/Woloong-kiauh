# ======================================================================= #
#  pip_install（自实现）：把 PyPI 包装进 Klipper 的 venv ✓
#
#  · 离线优先：WO_WHEELHOUSE 存在 -> 用 --no-index --find-links ✓
#  · 否则联网 pip install ✓
#  · remove 只卸**主包** ✓（不动依赖，避免误删其它组件共用的包 ✗）
#  · update = pip install --upgrade 主包 ✓
#  · 记录到 installed.json（service.py 负责 ✓）
# ======================================================================= #
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .base import HOME, ComponentError, ComponentService, Transaction, expand, run


class PipInstallService(ComponentService):
    method = "pip_install"

    # ---- 目标 venv ----
    def venv(self) -> Path:
        v = expand(self.spec.get("venv"))
        if not v:
            raise ComponentError("%s: 目录缺 venv" % self.id)
        return v

    def pip(self) -> Path:
        return self.venv() / "bin" / "pip"

    def packages(self):
        pkgs = self.spec.get("packages") or []
        if not pkgs:
            raise ComponentError("%s: 目录缺 packages" % self.id)
        return list(pkgs)

    def primary(self) -> str:
        p = self.spec.get("package_primary")
        if p:
            return p
        first = self.packages()[0]
        for sep in ("==", ">=", "<=", "~=", "!=", ">", "<"):
            if sep in first:
                return first.split(sep)[0]
        return first

    # ---- 状态 ----
    def status(self) -> dict:
        st = super().status()
        st["venv"] = str(self.venv())
        st["pip"] = self.pip().exists()
        st["primary"] = self.primary()
        return st

    def _pip(self, args) -> None:
        pip = self.pip()
        if not pip.exists():
            raise ComponentError("%s: 找不到 pip（%s）" % (self.id, pip))
        wh = Path(os.environ.get("WO_WHEELHOUSE") or (self.spec.get("wheelhouse") or ""))
        cmd = [str(pip), "install"]
        if str(wh) and wh.is_dir():
            cmd += ["--no-index", "--find-links", str(wh)]
        cmd += list(args)
        run(cmd)

    def _install(self, tx: Transaction) -> None:
        self._pip(self.packages())

    def _remove(self, tx: Transaction) -> None:
        pip = self.pip()
        if not pip.exists():
            return
        run([str(pip), "uninstall", "-y", self.primary()], check=False)

    def _update(self, tx: Transaction) -> None:
        self._pip(["--upgrade", self.primary()])
