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

from components.crowsnest.crowsnest import install_crowsnest
from components.klipper.services.klipper_setup_service import KlipperSetupService
from components.moonraker.services.moonraker_setup_service import MoonrakerSetupService
from components.webui_client.fluidd_data import FluiddData
from components.webui_client.mainsail_data import MainsailData
from components.webui_client.menus.client_install_menu import ClientInstallMenu
from components.webui_client.services.web_client_config_setup_service import (
    WebClientConfigSetupService,
)
from components.webui_client.services.web_client_setup_service import (
    WebClientSetupService,
)
from core.menus import Option
from core.menus.base_menu import BaseMenu
from core.types.color import Color


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class InstallMenu(BaseMenu):
    def __init__(self, previous_menu: Type[BaseMenu] | None = None) -> None:
        super().__init__()
        self.title = "Installation Menu"
        self.title_color = Color.GREEN
        self.previous_menu: Type[BaseMenu] | None = previous_menu
        self.klsvc = KlipperSetupService()
        self.mrsvc = MoonrakerSetupService()

    def set_previous_menu(self, previous_menu: Type[BaseMenu] | None) -> None:
        from core.menus.main_menu import MainMenu

        self.previous_menu = previous_menu if previous_menu is not None else MainMenu

    def set_options(self) -> None:
        # ★★ P45 菜单重设（2026-10-19 用户要求）：序号连续 ✓ 分类对齐 ✓ W) 置末 ✓
        #   Firmware & API  -> 1 Klipper / 2 Moonraker
        #   Webinterface    -> 3 Fluidd
        #   Client-Config   -> 4 Mainsail-Config / 5 Fluidd-Config
        #   Webcam Streamer -> 6 Crowsnest
        #   Woloong         -> W) 预置包（含 Woloong-mainsail / Woloong-klipperScreen / Woloong-kiauh ✓）
        #   已剔除：上游 Mainsail(3) / KlipperScreen(7) ✓（由 W) 提供 Woloong 版 ✓）
        self.options = {
            "1": Option(method=self.install_klipper),
            "2": Option(method=self.install_moonraker),
            "3": Option(method=self.install_fluidd),
            "4": Option(method=self.install_mainsail_config),
            "5": Option(method=self.install_fluidd_config),
            "6": Option(method=self.install_crowsnest),
            "w": Option(method=self.woloong_presets),
        }

    def print_menu(self) -> None:
        menu = textwrap.dedent(
            """
            ╟───────────────────────────────────────────────────────╢
            ║ Firmware & API:                                       ║
            ║  1) [Klipper]                                         ║
            ║  2) [Moonraker]                                       ║
            ║                                                       ║
            ║ Webinterface:                                         ║
            ║  3) [Fluidd]                                          ║
            ║                                                       ║
            ║ Client-Config:                                        ║
            ║  4) [Mainsail-Config]                                 ║
            ║  5) [Fluidd-Config]                                   ║
            ║                                                       ║
            ║ Webcam Streamer:                                      ║
            ║  6) [Crowsnest]                                       ║
            ╟───────────────────────────────────────────────────────╢
            ║  W) [Woloong Preset Bundles]                          ║
            """
        )[1:]
        print(menu, end="")
        # P45：说明放**框外** ✓（框内必须固定宽度 ✗，中文会撑歪 ✗）
        print(
            "  W) 内含：Woloong-mainsail（Web 界面）/ Woloong-klipperScreen（触屏 GUI）/ Woloong-kiauh（本工具）",
        )
        print("  （上游 Mainsail / KlipperScreen 已由上述 Woloong 版替代，故不再单列）")
        # ★ P45（2026-10-19）：去重说明放在**框外** ✓（框内宽度必须固定 ✗，中文会撑歪 ✗）

    def woloong_presets(self, **kwargs) -> None:
        # 档位预置包：本质是「批量安装」，故放在安装菜单内（而非主菜单另开入口 ✓）
        from core.menus.woloong_menu import WoloongTierMenu

        WoloongTierMenu(previous_menu=self.__class__).run()

    def install_klipper(self, **kwargs) -> None:
        self.klsvc.install()

    def install_moonraker(self, **kwargs) -> None:
        self.mrsvc.install()

    def install_mainsail(self, **kwargs) -> None:
        client: MainsailData = MainsailData()
        if client.client_dir.exists():
            ClientInstallMenu(client, self.__class__).run()
        else:
            WebClientSetupService("mainsail").install()

    def install_mainsail_config(self, **kwargs) -> None:
        WebClientConfigSetupService("mainsail").install()

    def install_fluidd(self, **kwargs) -> None:
        client: FluiddData = FluiddData()
        if client.client_dir.exists():
            ClientInstallMenu(client, self.__class__).run()
        else:
            WebClientSetupService("fluidd").install()

    def install_fluidd_config(self, **kwargs) -> None:
        WebClientConfigSetupService("fluidd").install()

    def install_crowsnest(self, **kwargs) -> None:
        install_crowsnest()
