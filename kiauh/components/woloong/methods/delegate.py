# ======================================================================= #
#  委托上游：**不重复实现** kiauh 已有的组件 ✓
#
#  设计原则（P89）：
#   · 上游已有的装/卸/更，一律**调用上游** ✓（避免两套实现打架 ✗）
#   · 我们只做「目录统一 + 事务 + 门禁」✓
#   · 上游函数内部会自行交互/提示；CLI 场景下一律传 interactive=False ✓
# ======================================================================= #
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict

from .base import ComponentError, ComponentService, Transaction, expand


def _klipper_install() -> None:
    from components.klipper.services.klipper_setup_service import KlipperSetupService

    if not KlipperSetupService().install(count=1, interactive=False):
        raise ComponentError("klipper: 上游 install 返回 False")


def _klipper_remove() -> None:
    from components.klipper.services.klipper_setup_service import KlipperSetupService

    svc = KlipperSetupService()
    if not svc.remove(remove_service=True, remove_dir=True, remove_env=True, remove_all=True, interactive=False):
        raise ComponentError("klipper: 上游 remove 返回 False")


def _klipper_update() -> None:
    from components.klipper.services.klipper_setup_service import KlipperSetupService

    if not KlipperSetupService().update(interactive=False):
        raise ComponentError("klipper: 上游 update 返回 False")


def _moonraker_install() -> None:
    from components.moonraker.services.moonraker_setup_service import MoonrakerSetupService

    if not MoonrakerSetupService().install(interactive=False):
        raise ComponentError("moonraker: 上游 install 返回 False")


def _moonraker_remove() -> None:
    from components.moonraker.services.moonraker_setup_service import MoonrakerSetupService

    svc = MoonrakerSetupService()
    if not svc.remove(remove_service=True, remove_dir=True, remove_env=True, remove_polkit=True, remove_all=True, interactive=False):
        raise ComponentError("moonraker: 上游 remove 返回 False")


def _moonraker_update() -> None:
    from components.moonraker.services.moonraker_setup_service import MoonrakerSetupService

    if not MoonrakerSetupService().update(interactive=False):
        raise ComponentError("moonraker: 上游 update 返回 False")


def _klipperscreen_install() -> None:
    from components.klipperscreen.klipperscreen import install_klipperscreen

    install_klipperscreen()


def _klipperscreen_remove() -> None:
    from components.klipperscreen.klipperscreen import remove_klipperscreen

    remove_klipperscreen()


def _klipperscreen_update() -> None:
    from components.klipperscreen.klipperscreen import update_klipperscreen

    update_klipperscreen()


def _crowsnest_install() -> None:
    from components.crowsnest.crowsnest import install_crowsnest

    install_crowsnest()


def _crowsnest_remove() -> None:
    from components.crowsnest.crowsnest import remove_crowsnest

    remove_crowsnest()


def _crowsnest_update() -> None:
    from components.crowsnest.crowsnest import update_crowsnest

    update_crowsnest()



def _mainsail_cfg_install() -> None:
    from components.webui_client.services.web_client_config_setup_service import (
        WebClientConfigSetupService,
    )

    if not WebClientConfigSetupService("mainsail").install(interactive=False):
        raise ComponentError("mainsail-config: 上游 install 返回 False")


def _mainsail_cfg_remove() -> None:
    from components.webui_client.services.web_client_config_setup_service import (
        WebClientConfigSetupService,
    )

    if not WebClientConfigSetupService("mainsail").remove(backup_config=True):
        raise ComponentError("mainsail-config: 上游 remove 返回 False")


def _mainsail_cfg_update() -> None:
    from components.webui_client.services.web_client_config_setup_service import (
        WebClientConfigSetupService,
    )

    if not WebClientConfigSetupService("mainsail").update(interactive=False):
        raise ComponentError("mainsail-config: 上游 update 返回 False")

DELEGATES: Dict[str, Dict[str, Callable[[], None]]] = {
    "klipper": {"install": _klipper_install, "remove": _klipper_remove, "update": _klipper_update},
    "moonraker": {"install": _moonraker_install, "remove": _moonraker_remove, "update": _moonraker_update},
    "klipperscreen": {
        "install": _klipperscreen_install,
        "remove": _klipperscreen_remove,
        "update": _klipperscreen_update,
    },
    "crowsnest": {"install": _crowsnest_install, "remove": _crowsnest_remove, "update": _crowsnest_update},
    "mainsail-config": {
        "install": _mainsail_cfg_install,
        "remove": _mainsail_cfg_remove,
        "update": _mainsail_cfg_update,
    },
}


class DelegateService(ComponentService):
    """把装/卸/更转交给上游实现 ✓（本类负责事务 + **后置条件校验** ✓）。

    ★ P98（2026-10-22 真机 ✗）：上游函数**内部吞异常** ✗（只打印 [ERROR] 就返回 ✗）
      -> 只看「没抛异常」会**假成功** ✗（实测 klipperscreen 安装脚本失败仍报 ✓ ✗✗）
      -> 修：装/卸后**校验真实状态**（target_path 是否存在 ✓）；不达标就抛错 ✗
    """

    method = "delegate"

    def _target(self):
        from .base import expand

        return expand(self.spec.get("target_path"))

    def _unit_exists(self) -> bool:
        svc = self.spec.get("service")
        if not svc:
            return True
        for base in ("/etc/systemd/system", "/lib/systemd/system", "/usr/lib/systemd/system"):
            if Path(base, svc + ".service").exists():
                return True
        return False

    def _check(self, action: str) -> None:
        """★ P98b：只看 target 目录不够 ✗（clone 成功但安装脚本失败 ✗）
        -> 还要看 venv 与 systemd 单元 ✓（这两个是「真的装上了」的硬证据 ✓）"""
        t = self._target()
        venv = expand(self.spec.get("venv"))
        if action == "install":
            if t is not None and not t.exists():
                raise ComponentError(
                    "%s: 上游 install 未落地（%s 不存在 ✗；多为 sudo 需密码/依赖缺失 ✗）" % (self.id, t)
                )
            if venv is not None and not (venv / "bin" / "python").exists():
                raise ComponentError("%s: 上游 install 未建 venv（%s ✗）" % (self.id, venv))
            if not self._unit_exists():
                raise ComponentError("%s: 上游 install 未创建 systemd 单元（%s ✗）" % (self.id, self.spec.get("service")))
        elif action == "remove":
            if t is not None and t.exists():
                raise ComponentError("%s: 上游 remove 后 %s 仍存在 ✗" % (self.id, t))
            if venv is not None and (venv / "bin" / "python").exists():
                raise ComponentError("%s: 上游 remove 后 venv 仍存在 ✗" % self.id)

    def _call(self, action: str) -> None:
        table = DELEGATES.get(self.id)
        if not table:
            raise ComponentError("%s: 未登记上游委托" % self.id)
        fn = table.get(action)
        if not fn:
            raise ComponentError("%s: 上游不支持 %s" % (self.id, action))
        fn()
        self._check(action)

    def _install(self, tx: Transaction) -> None:
        self._call("install")

    def _remove(self, tx: Transaction) -> None:
        self._call("remove")

    def _update(self, tx: Transaction) -> None:
        self._call("update")


def is_delegated(component_id: str) -> bool:
    return component_id in DELEGATES
