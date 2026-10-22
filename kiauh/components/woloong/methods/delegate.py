# ======================================================================= #
#  委托上游：**不重复实现** kiauh 已有的组件 ✓
#
#  设计原则（P89）：
#   · 上游已有的装/卸/更，一律**调用上游** ✓（避免两套实现打架 ✗）
#   · 我们只做「目录统一 + 事务 + 门禁」✓
#   · 上游函数内部会自行交互/提示；CLI 场景下一律传 interactive=False ✓
# ======================================================================= #
from __future__ import annotations

from typing import Callable, Dict

from .base import ComponentError, ComponentService, Transaction


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


DELEGATES: Dict[str, Dict[str, Callable[[], None]]] = {
    "klipper": {"install": _klipper_install, "remove": _klipper_remove, "update": _klipper_update},
    "moonraker": {"install": _moonraker_install, "remove": _moonraker_remove, "update": _moonraker_update},
    "klipperscreen": {
        "install": _klipperscreen_install,
        "remove": _klipperscreen_remove,
        "update": _klipperscreen_update,
    },
    "crowsnest": {"install": _crowsnest_install, "remove": _crowsnest_remove, "update": _crowsnest_update},
}


class DelegateService(ComponentService):
    """把装/卸/更转交给上游实现 ✓（本类只管事务记录）。"""

    method = "delegate"

    def _call(self, action: str) -> None:
        table = DELEGATES.get(self.id)
        if not table:
            raise ComponentError("%s: 未登记上游委托" % self.id)
        fn = table.get(action)
        if not fn:
            raise ComponentError("%s: 上游不支持 %s" % (self.id, action))
        fn()

    def _install(self, tx: Transaction) -> None:
        self._call("install")

    def _remove(self, tx: Transaction) -> None:
        self._call("remove")

    def _update(self, tx: Transaction) -> None:
        self._call("update")


def is_delegated(component_id: str) -> bool:
    return component_id in DELEGATES
