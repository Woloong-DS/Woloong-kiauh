# ======================================================================= #
#  Copyright (C) 2020 - 2026 Dominik Willner <dev.dw-0@proton.me>         #
#                                                                         #
#  This file is part of KIAUH - Klipper Installation And Update Helper    #
#  https://github.com/dw-0/kiauh                                          #
#                                                                         #
#  This file may be distributed under the terms of the GNU GPLv3 license  #
# ======================================================================= #

from __future__ import annotations

from typing import Any, List

import core.menus.install_menu as install_menu_module
import pytest
from core.menus.install_menu import InstallMenu


@pytest.fixture
def menu(monkeypatch: pytest.MonkeyPatch) -> InstallMenu:
    # Avoid the heavyweight singleton setup services loading real instances.
    monkeypatch.setattr(install_menu_module, "KlipperSetupService", lambda: object())
    monkeypatch.setattr(install_menu_module, "MoonrakerSetupService", lambda: object())
    return InstallMenu()


def _fake_data(client_dir_exists: bool) -> Any:
    return type(
        "Client",
        (),
        {
            "client_dir": type(
                "P",
                (),
                {"exists": lambda self: client_dir_exists},
            )(),
        },
    )()


class TestInstallMenuWiring:
    def test_options_expose_every_install_entry(self, menu: InstallMenu) -> None:
        # P45/P87（去重设计）：上游 [Mainsail] / [KlipperScreen] 入口已剔除 ✗
        #   由安装菜单的 w) [Woloong Preset Bundles] 提供 Woloong 版 ✓
        #   故选项集 = 1 klipper / 2 moonraker / 3 fluidd / 4 mainsail-config
        #             5 fluidd-config / 6 crowsnest / w presets
        for key in ("1", "2", "3", "4", "w"):
            assert key in menu.options

    def test_set_previous_menu_defaults_to_main_menu(
        self, menu: InstallMenu, monkeypatch
    ) -> None:
        # importing MainMenu here avoids an import cycle in the module under test
        from core.menus.main_menu import MainMenu

        menu.set_previous_menu(None)
        assert menu.previous_menu is MainMenu

    def test_install_mainsail_config_delegates_to_config_service(
        self, menu: InstallMenu, monkeypatch
    ) -> None:
        calls: List[Any] = []
        monkeypatch.setattr(
            install_menu_module,
            "WebClientConfigSetupService",
            lambda name: type(
                "S", (), {"install": lambda self: calls.append(name) or True}
            )(),
        )

        menu.install_mainsail_config()

        assert calls == ["mainsail"]

    def test_no_upstream_klipperscreen_or_mainsail_entry(self, menu: InstallMenu) -> None:
        """整合决议 v1.0：安装菜单**不存在**上游 KlipperScreen / Mainsail 入口。

        两者已由 W) 预置包里的 Woloong 版替代；若重新出现，就会重演
        「把我们的软件当上游装」或「同一软件两个入口」的老问题。
        """
        assert set(menu.options) == {"1", "2", "3", "4", "w", "b"}
        # 整合决议 v1.0：上游 Mainsail / KlipperScreen / Fluidd 入口一律不存在 ✗
        for name in ("install_klipperscreen", "install_mainsail", "install_fluidd"):
            assert not hasattr(InstallMenu, name)

    def test_crowsnest_delegate(self, menu: InstallMenu, monkeypatch) -> None:
        calls: List[str] = []
        monkeypatch.setattr(
            install_menu_module, "install_crowsnest", lambda: calls.append("cn")
        )

        menu.install_crowsnest()

        assert calls == ["cn"]