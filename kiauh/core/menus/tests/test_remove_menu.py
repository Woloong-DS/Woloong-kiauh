from __future__ import annotations

import pytest
from core.menus.remove_menu import RemoveMenu


@pytest.fixture
def menu() -> RemoveMenu:
    return RemoveMenu()


class TestRemoveMenuEntries:
    def test_has_woloong_entry(self, menu: RemoveMenu) -> None:
        # OI-015：安装菜单有 W) 入口，卸载菜单必须也有 ✓
        assert "w" in menu.options

    def test_woloong_entry_opens_manage_menu(self, menu: RemoveMenu, monkeypatch) -> None:
        import core.menus.woloong_manage_menu as mod

        called = {}

        class FakeManage:
            def __init__(self, previous_menu=None):
                called['prev'] = previous_menu

            def run(self):
                called['ran'] = True

        monkeypatch.setattr(mod, 'WoloongManageMenu', FakeManage)
        menu.woloong_manage()
        assert called.get('ran') is True

    def test_menu_lines_fit_box(self, menu: RemoveMenu, capsys) -> None:
        menu.print_menu()
        lines = [ln for ln in capsys.readouterr().out.splitlines() if ln]
        too_wide = [ln for ln in lines if len(ln) > 57]
        assert not too_wide, too_wide
        assert any('W) [Woloong Preset Bundles]' in ln for ln in lines)
