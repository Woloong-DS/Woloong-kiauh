# ======================================================================= #
#  Copyright (C) 2020 - 2026 Dominik Willner <dev.dw-0@proton.me>         #
#                                                                         #
#  This file is part of KIAUH - Klipper Installation And Update Helper    #
#  https://github.com/dw-0/kiauh                                          #
#                                                                         #
#  This file may be distributed under the terms of the GNU GPLv3 license  #
# ======================================================================= #

from __future__ import annotations

import textwrap
from typing import Type

from components.crowsnest.crowsnest import remove_crowsnest
from components.klipper.menus.klipper_remove_menu import KlipperRemoveMenu
from components.moonraker.menus.moonraker_remove_menu import (
    MoonrakerRemoveMenu,
)
from components.webui_client.services.web_client_config_setup_service import (
    WebClientConfigSetupService,
)
from core.menus import Option
from core.menus.base_menu import BaseMenu
from core.types.color import Color


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class RemoveMenu(BaseMenu):
    def __init__(self, previous_menu: Type[BaseMenu] | None = None) -> None:
        super().__init__()
        self.title = "Remove Menu"
        self.title_color = Color.RED
        self.previous_menu: Type[BaseMenu] | None = previous_menu

    def set_previous_menu(self, previous_menu: Type[BaseMenu] | None) -> None:
        from core.menus.main_menu import MainMenu

        self.previous_menu = previous_menu if previous_menu is not None else MainMenu

    def set_options(self) -> None:
        self.options = {
            "1": Option(method=self.remove_klipper),
            "2": Option(method=self.remove_moonraker),
            "3": Option(method=self.remove_crowsnest),
            # P87（2026-10-22）：可装必可卸 —— 配置类此前只能装、卸不了
            "4": Option(method=self.remove_mainsail_config),
            # ★ OI-015（2026-10-23）：安装菜单有 W) 入口，卸载菜单却没有 ✗
            #   可选组件只能绕：Install → W) → m) → 选组件 → remove ✗（不属于“卸载”入口）
            "w": Option(method=self.woloong_manage),
        }

    def print_menu(self) -> None:
        menu = textwrap.dedent(
            """
            ╟───────────────────────────────────────────────────────╢
            ║ INFO: Configurations and/or any backups will be kept! ║
            ╟───────────────────────────────────────────────────────╢
            ║ Firmware & API:                                       ║
            ║  1) [Klipper]                                         ║
            ║  2) [Moonraker]                                       ║
            ║                                                       ║
            ║ Webcam Streamer:                                      ║
            ║  3) [Crowsnest]                                       ║
            ║                                                       ║
            ║ Client-Config:                                        ║
            ║  4) [Mainsail-Config]                                 ║
            ╟───────────────────────────────────────────────────────╢
            ║  W) [Woloong Preset Bundles]                          ║
            """
        )[1:]
        print(menu, end="")

    def woloong_manage(self, **kwargs) -> None:
        # 组件管理菜单：安装 / 卸载 / 更新 / 状态（可选组件都在这里 ✓）
        from core.menus.woloong_manage_menu import WoloongManageMenu

        WoloongManageMenu(previous_menu=self.__class__).run()

    def remove_klipper(self, **kwargs) -> None:
        KlipperRemoveMenu(previous_menu=self.__class__).run()

    def remove_moonraker(self, **kwargs) -> None:
        MoonrakerRemoveMenu(previous_menu=self.__class__).run()

    def remove_crowsnest(self, **kwargs) -> None:
        remove_crowsnest()

    def remove_mainsail_config(self, **kwargs) -> None:
        WebClientConfigSetupService("mainsail").remove()

    def remove_fluidd_config(self, **kwargs) -> None:
        WebClientConfigSetupService("fluidd").remove()
