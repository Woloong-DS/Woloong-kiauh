# ======================================================================= #
#  Woloong 组件管理菜单（方案 A）
#
#  用户判据：Woloong-kiauh 要能「安装 / 管理 / 卸载」全部组件 ✓
#  本菜单列出**目录里的全部组件**（数据驱动 ✓），逐项提供：
#    1) 安装  2) 卸载  3) 更新  4) 状态
#
#  能力标签（native/delegate/blocked）直接展示 ✓，blocked 显示理由 ✓ 且**禁止安装** ✗
# ======================================================================= #
from __future__ import annotations

from typing import Type

from core.logger import Logger
from core.menus import Option
from core.menus.base_menu import BaseMenu
from core.types.color import Color


class WoloongManageMenu(BaseMenu):
    def __init__(self, previous_menu: Type[BaseMenu] | None = None, **kwargs) -> None:
        super().__init__()
        self.title = "Woloong 组件管理"
        self.title_color = Color.GREEN
        self.previous_menu = previous_menu
        self.items: list[str] = []
        self._load()

    # ---------- 数据 ----------
    def _load(self) -> None:
        from components.woloong import catalog
        from components.woloong.methods import capability

        self.comps = catalog.load()
        self.caps = {cid: capability(cid) for cid in self.comps}
        self.items = sorted(self.comps)

    def set_previous_menu(self, previous_menu: Type[BaseMenu] | None) -> None:
        from core.menus.main_menu import MainMenu

        self.previous_menu = previous_menu if previous_menu is not None else MainMenu

    def set_options(self) -> None:
        opts = {str(i + 1): Option(method=self._pick, opt_index=i) for i in range(len(self.items))}
        opts["b"] = Option(method=self._back)
        self.options = opts

    def print_menu(self) -> None:
        from components.woloong.methods import SUPPORTED

        print(Color.apply("  能力：native=仓库内实现 / delegate=委托上游 / blocked=不可运行期安装", Color.CYAN))
        print("  " + "-" * 66)
        for i, cid in enumerate(self.items, 1):
            cap = self.caps[cid]
            tag = {"native": "✓native", "delegate": "→delegate", "blocked": "✗blocked"}.get(cap, cap)
            name = self.comps[cid].get("name") or cid
            print("  %2d) %-22s %-14s %s" % (i, cid, tag, name))
        print("  " + "-" * 66)
        print(Color.apply("  能力：native=仓库内实现 / delegate=委托上游 / blocked=不可运行期安装", Color.CYAN))

    # ---------- 动作 ----------
    def _back(self, **kwargs) -> None:
        self._jump_back()

    def _pick(self, **kwargs) -> None:
        idx = kwargs.get("opt_index")
        if idx is None or not (0 <= idx < len(self.items)):
            return
        cid = self.items[idx]
        cap = self.caps[cid]
        print("\n  组件：%s（%s）" % (cid, self.comps[cid].get("name") or cid))
        print("  能力：%s" % cap)
        if cap == "blocked":
            reason = self.comps[cid].get("blocked_reason") or "（未登记理由）"
            Logger.print_warn("该组件不可运行期安装：%s" % reason)
            input("\n按回车继续 ...")
            return
        print("   1) 安装   2) 卸载   3) 更新   4) 状态")
        try:
            ans = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        act = {"1": "install", "2": "remove", "3": "update", "4": "status"}.get(ans)
        if not act:
            return
        self._run(cid, cap, act)
        input("\n按回车继续 ...")

    def _run(self, cid: str, cap: str, act: str) -> None:
        from components.woloong import service

        try:
            if act == "status":
                st = service.component_status(cid)
                Logger.print_info("状态：%s" % st)
                return
            if act == "install":
                Logger.print_status("安装 %s ..." % cid)
                service.install_component(cid)
                Logger.print_ok("%s 安装完成 ✓" % cid)
            elif act == "remove":
                Logger.print_status("卸载 %s ..." % cid)
                service.remove_component(cid)
                Logger.print_ok("%s 卸载完成 ✓" % cid)
            else:
                Logger.print_status("更新 %s ..." % cid)
                service.update_component(cid)
                Logger.print_ok("%s 更新完成 ✓" % cid)
        except Exception as exc:  # noqa: BLE001
            Logger.print_error("%s %s 失败：%s" % (cid, act, exc))
