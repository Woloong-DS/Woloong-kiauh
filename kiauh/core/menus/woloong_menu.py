from __future__ import annotations

import json
import pathlib
import os
import subprocess
from pathlib import Path
from typing import Type

from core.logger import Logger
from core.menus.base_menu import BaseMenu, FooterType, Option
from core.types.color import Color
from utils.input_utils import get_confirm

WO_OFFLINE_ROOT = Path(os.environ.get("WO_OFFLINE_ROOT", "/opt/woloong"))
WO_MANIFEST = WO_OFFLINE_ROOT.joinpath("manifest", "stack.json")
WO_INSTALLER = WO_OFFLINE_ROOT.joinpath("install", "woloong-base-install")
# 安装器的 state 记录（唯一可靠判据 ✓）
WO_STATE = WO_OFFLINE_ROOT.joinpath("state", "installed.json")

TIER_ORDER = ["mono_basic", "mono_advanced", "multicolor_basic", "multicolor_advanced"]
# 标签只用 ASCII：终端里 CJK 是双宽，会撑破自算的框线（与 KIAUH 美术字同一类坑 ✓）
# 中文档位名（用户可读 ✓）；注意 **CJK 是双宽**，排版必须按显示宽度算（见 _dwidth ✓）
TIER_LABEL = {
    "mono_basic": "单色·基础（必选）",
    "mono_advanced": "单色·进阶",
    "multicolor_basic": "多色·基础",
    "multicolor_advanced": "多色·进阶",
}
# ★ 2026-10-18 用户指出：详情页曾直接打印**组件 id**（mainsail / klipperscreen）✗，
#   与安装菜单里的 Woloong Mainsail / Woloong KlipperScreen 不一致 → 看起来像"重复的软件" ✗。
#   品牌资源（woloong-theme / woloong-ks-theme）也被单独列出 ✗，实际内置在前两者里。
#   → 统一用 DISPLAY_NAME 展示 ✓；DERIVED 里的条目**合并进父项**、不单列、不计入项数 ✓。
DISPLAY_NAME = {
    "klipper": "Klipper",
    "moonraker": "Moonraker",
    "mainsail": "Woloong Mainsail",
    "mainsail-config": "Woloong Mainsail-Config",
    "klipperscreen": "Woloong KlipperScreen",
    "crowsnest": "Crowsnest",
    "KAMP": "KAMP",
    "gcode_shell_command": "Gcode-Shell-Command",
    "can_stack": "CAN 支持（镜像级）",
    "mcu_toolchain": "MCU 工具链（镜像级）",
    "shaketune": "Shake&Tune",
    "spoolman": "Spoolman",
    "klipper_backup": "Klipper-Backup",
    "z_calibration": "Z-Calibration",
    "led_effect": "LED-Effect",
    "tmc_autotune": "TMC-Autotune",
    "auto_speed": "Auto-Speed",
    "cartographer_plugin": "Cartographer 插件",
    "cartographer_firmware": "Cartographer 固件",
    "katapult": "Katapult",
    "fluidd": "Fluidd",
    "timelapse": "Timelapse",
    "telegram_bot": "Telegram 通知",
    "kiauh": "Woloong-KIAUH",
    "afc": "AFC",
    "afc_klipperscreen": "AFC 界面（KlipperScreen）",
    "mainsail_afc": "Mainsail-AFC",
    "at_docs": "AFC 离线文档",
    "woloong-theme": "Woloong Mainsail 品牌主题",
    "woloong-ks-theme": "Woloong KlipperScreen 品牌主题",
}

# 品牌资源 → 合并进父项（不单列 ✓、不计入项数 ✓）
DERIVED = {
    "woloong-theme": "mainsail",
    "woloong-ks-theme": "klipperscreen",
}

def display_of(cid: str) -> str:
    """用户可见名称（绝不回退成裸 id ✗ → 那样又会出现 mainsail/klipperscreen ✗）。"""
    return DISPLAY_NAME.get(cid) or cid

def listed(tier_items: list) -> list:
    """该档位**应当在界面上列出**的组件（剔除内置品牌资源 ✓）。"""
    return [c for c in tier_items if c not in DERIVED]



def _dwidth(text: str) -> int:
    """字符串在终端里的**显示宽度**（CJK/全角算 2 列 ✓）。"""
    import unicodedata

    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _dpad(text: str, width: int) -> str:
    """按显示宽度右侧补空格到 width ✓（不能用 ljust：它按字符数算 ✗）。"""
    return text + " " * max(0, width - _dwidth(text))


def load_manifest() -> dict:
    try:
        return json.loads(WO_MANIFEST.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_tiers() -> dict[str, list[str]]:
    """从离线包 manifest 读取档位 -> 组件列表；读不到则返回空 dict（不抛异常）。"""
    data = load_manifest()
    tiers = data.get("tiers") or {}
    out: dict[str, list[str]] = {}
    for name, spec in tiers.items():
        items = spec.get("items") if isinstance(spec, dict) else spec
        out[str(name)] = [str(x) for x in (items or [])]
    return out


class WoloongTierMenu(BaseMenu):
    """Woloong 预置包菜单：按 manifest 的 tiers 离线安装（事务/回滚由安装器负责）。

    定位（2026-10-17 用户确认）：镜像里 mono_basic 的 11 项已全部就位 ✓，
    所以本菜单**不是"首次安装"**，而是「重装 / 切换打印方式 / 修复」——
    因此每行标注 (总项数, 已就位项数)，并在执行前给出「将装 X 项、跳过 Y 项」的确认页 ✓。
    """

    def __init__(self, **kwargs) -> None:
        # 注意：KIAUH 的菜单会被以 previous_menu=... 构造（PTY 渲染测试暴露过这个失败点 ✓）
        super().__init__(**kwargs)
        self.header = True
        self.title = "Woloong Presets"
        self.title_color = Color.CYAN
        self.footer_type = FooterType.BACK
        self.input_label_txt = "选择预置包"
        self.tiers = load_tiers()
        self.names = [n for n in TIER_ORDER if n in self.tiers] or sorted(self.tiers)
        self.components: dict = load_manifest().get("components") or {}
        self._state: set[str] = self._load_state()

    def set_previous_menu(self, previous_menu: Type[BaseMenu] | None) -> None:
        # KIAUH 约定：抽象方法，必须实现；默认返回主菜单（b 键回退用 ✓）
        from core.menus.main_menu import MainMenu

        self.previous_menu = previous_menu if previous_menu is not None else MainMenu

    # ---------- 已就位判定 ----------
    def _load_state(self) -> set[str]:
        """读取安装器的 state 记录（**唯一可靠判据** ✓）。

        2026-10-17 上机核对发现两个坑 ✗：
          1) 用 target_path 存在性判断是错的 —— 很多组件（led_effect / tmc_autotune /
             auto_speed / cartographer_plugin …）的 target_path 是**共享目录**
             ~/klipper/klippy/extras/ ✗，目录永远存在 → 全部误判为"已就位" ✗
          2) 安装器用的是 state/installed.json + 文件 sha256 校验 ✓（见 lib/methods.sh
             component_is_installed）→ 菜单必须与它**同源** ✓，否则菜单说"已就位"
             而安装器仍会重装 ✗，行为与显示不一致 ✗
        故此处只认 installed.json 的 key ✓；image_level 组件由镜像烘焙、不产生 state，
        单独视为就位 ✓。
        """
        try:
            data = json.loads(WO_STATE.read_text(encoding="utf-8"))
            return set(data.keys()) if isinstance(data, dict) else set()
        except Exception:
            return set()

    def _display(self, cid: str) -> str:
        """用户可见名：**优先 manifest 的 display_name** ✓（单一数据源 ✓），
        回退本地 DISPLAY_NAME ✓（离线包 manifest 缺字段时不至于显示裸 id ✗）。"""
        spec = self.components.get(cid) or {}
        return str(spec.get("display_name") or display_of(cid))

    def _derived_parent(self, cid: str) -> str:
        spec = self.components.get(cid) or {}
        return str(spec.get("derived_from") or DERIVED.get(cid) or "")

    def _present(self, cid: str) -> bool:
        """该组件是否已安装 —— **证据判据** ✓（不再只认 state ✗）。

        ★ 2026-10-18 用户 docx P21/P22：
          ① `14. Woloong-KIAUH [待安装]` —— KIAUH 明明已烘焙进镜像 ✗
             （没有它根本进不到这个页面 ✗）→ 自相矛盾 ✗
          ② `3. Spoolman` 在不同页面显示不同状态 ✗
          根因：`_present` **只**查 state/installed.json ✗，
          而 `install_kiauh` / `install_spoolman` / `install_kamp` 等
          **专用 provisioning 函数不写 state** ✗ → 实装却报「待安装」✗
        修：state ✓ 或 image_level ✓ 或 **表里的 install_dir 真实存在** ✓
            或 **表里的 config_file 真实存在** ✓ —— 四者之一即视为已就位 ✓
        """
        if cid in self._state:
            return True
        spec = self.components.get(cid) or {}
        if spec.get("install_method") == "image_level":
            return True
        d = str(spec.get("install_dir") or "")
        if d:
            try:
                if pathlib.Path(d).exists():
                    return True
            except Exception:
                pass
        cf = str(spec.get("config_file") or "")
        cdir = str(spec.get("config_dir") or "config")
        if cf and not cdir.startswith("/"):
            try:
                if pathlib.Path("/home/pi/printer_data", cdir, cf).exists():
                    return True
            except Exception:
                pass
        return False

    def _listed(self, tier: str) -> list:
        """该档位在界面上列出的组件（剔除 derived_from ✓，并**去重** ✓）。

        ★ 2026-10-18 修 P17：同一组件可能出现在多个档位（如 spoolman）✗ → 必须去重 ✓。
        """
        out, seen = [], set()
        for c in self.tiers.get(tier, []) or []:
            if self._derived_parent(c):
                continue
            if c in seen:
                continue
            seen.add(c)
            out.append(c)
        return out

    def _counts(self, tier: str) -> tuple[int, int]:
        # ★ 只统计「界面上列出」的组件 ✓（内置品牌资源已并入父项，不重复计数 ✗）
        comps = self._listed(tier)
        return sum(1 for c in comps if self._present(c)), len(comps)

    # ---------- 选项 ----------
    def _make_install(self, tier: str):
        """闭包传参：KIAUH 的 Option 不接受自定义关键字参数（渲染测试暴露 ✓）。"""

        def _run(**kwargs) -> None:
            self._install_tier(tier)

        return _run

    def set_options(self) -> None:
        self.options = {}
        for idx, name in enumerate(self.names, start=1):
            self.options[str(idx)] = Option(method=self._make_install(name))
        self.options["d"] = Option(method=self._dry_run)
        self.options["i"] = Option(method=self._show_items)

    # ---------- 渲染 ----------
    def print_menu(self) -> None:
        if not self.tiers:
            Logger.print_warn(f"Preset manifest not found: {WO_MANIFEST}")
            Logger.print_info("It ships with the offline package; missing means the package is incomplete.")
            return
        # 版式：**按显示宽度**排版（CJK 是双宽 ✓，不能用 len/ljust ✗），再按固定内宽补框 ✓
        rows: list[str] = []
        for idx, name in enumerate(self.names, start=1):
            label = TIER_LABEL.get(name, name)
            have, total = self._counts(name)
            mark = "全部就绪" if have == total else f"待装 {total - have} 项"
            left = _dpad(f"{idx}) {label}", 24)
            cnt = _dpad(f"{have:>2}/{total:<2} 已就位", 13)
            rows.append(left + cnt + "  " + mark)
        rows.append("i) 查看某预置包的组件清单（输入编号）")
        rows.append("d) 仅预览（dry-run，不做任何改动）")
        # 与 BaseMenu 的统一框宽对齐：内宽 55（整行 57 ✓）
        WIDE = 55
        for r in rows:
            assert _dwidth(r) <= WIDE - 2, "row too wide for 57-col box: " + r
        inner = WIDE
        # BaseMenu 已画标题框（╔═╗），这里只画分隔线 ✓
        print("╟" + "─" * inner + "╢")
        for r in rows[:-2]:
            print("║ " + _dpad(r, inner - 2) + " ║")
        print("╟" + "─" * inner + "╢")
        for r in rows[-2:]:
            print("║ " + _dpad(r, inner - 2) + " ║")
        print("╟" + "─" * inner + "╢")

    # ---------- 动作 ----------
    def _run_installer(self, args: list[str]) -> int:
        if not WO_INSTALLER.is_file():
            Logger.print_error(f"Installer not found: {WO_INSTALLER}")
            return 127
        # ★ 2026-10-18 上机实测：安装器要求 root ✓，但这里没加 sudo ✗ →
        #   「预置包安装」与「仅预览(d)」**全部失败**（[FAIL] 需要 root 权限 ✗）。
        #   KIAUH 自身约定一律用 ["sudo", ...]（见 utils/sys_utils.py:325/390/548）✓。
        cmd = ["sudo", "bash", str(WO_INSTALLER), *args]
        Logger.print_status("Running: " + " ".join(cmd))
        return subprocess.call(cmd)

    def _install_tier(self, tier: str) -> None:
        comps = self.tiers.get(tier, [])
        have, total = self._counts(tier)
        Logger.print_status(
            f"预置包 [{TIER_LABEL.get(tier, tier)}]：共 {total} 项，已就位 {have} 项，将安装 {total - have} 项"
        )
        if have == total:
            Logger.print_info("该预置包全部已就位；继续将执行【重装】")
        if not get_confirm(f"确认安装预置包 {TIER_LABEL.get(tier, tier)}？", default_choice=False):
            return
        rc = self._run_installer(["--tier", tier])
        if rc == 0:
            Logger.print_ok(f"预置包 [{TIER_LABEL.get(tier, tier)}] 安装完成 ✓")
        else:
            Logger.print_error(
                f"Preset [{tier}] failed (rc={rc}); installer rolled back per its transaction semantics."
            )
        input("\n按回车继续 ...")

    def _show_items(self, **kwargs) -> None:  # KIAUH 会传 opt_index= ✓
        Logger.print_status("查看哪个预置包？(1-%d)" % len(self.names))
        try:
            ans = input("> ").strip()
            idx = int(ans) - 1
            if not 0 <= idx < len(self.names):
                raise ValueError
        except Exception:
            Logger.print_warn("编号无效")
            return
        name = self.names[idx]
        items = self._listed(name)                # 剔除内置品牌资源 ✓（按 manifest.derived_from ✓）
        merged = [c for c in self.tiers[name] if c in DERIVED]
        Logger.print_status(f"预置包 [{TIER_LABEL.get(name, name)}] 组件清单（共 {len(items)} 项）：")
        for i, cid in enumerate(items, start=1):
            spec = self.components.get(cid) or {}
            role = str(spec.get("role") or "")
            state = "已就位" if self._present(cid) else "待安装"
            # 显示名 + **按显示宽度对齐** ✓（中文双宽 ✗，不能用 f"{x:<26}" ✗）
            print(f"  {i:>2}. {_dpad(self._display(cid), 26)} [{state}]  {role[:42]}")
        if merged:
            print("")
            Logger.print_info("已内置、不单独列示：" + "，".join(
                f"{display_of(c)}（随 {display_of(DERIVED[c])} ✓）" for c in merged))
        # ① 单组件安装/修复（用户要求：不必为一个故障组件重装整包 ✓）
        Logger.print_info("可直接输入序号，只安装/修复**该组件**（强制重装，--force ✓）；直接回车返回")
        try:
            pick = input("> ").strip()
        except Exception:
            return
        if not pick:
            return
        try:
            k = int(pick) - 1
            if not 0 <= k < len(items):
                raise ValueError
        except Exception:
            Logger.print_warn("序号无效，已返回")
            return
        cid = items[k]
        Logger.print_status(f"将强制重装单个组件 [{self._display(cid)}]（id={cid}；只影响它，不动其余 {len(items) - 1} 项 ✓）")
        if not get_confirm(f"确认安装/修复 [{self._display(cid)}]？", default_choice=False):
            return
        rc = self._run_installer(["--component", cid, "--force"])
        if rc == 0:
            Logger.print_ok(f"[{self._display(cid)}] 安装/修复完成 ✓")
            self._state = self._load_state()
        else:
            Logger.print_error(f"[{self._display(cid)}] 失败（rc={rc}）；安装器已按其事务语义回滚 ✓")
        input("\n按回车继续 ...")

    def _dry_run(self, **kwargs) -> None:
        for name in self.names:
            rc = self._run_installer(["--tier", name, "--dry-run"])
            if rc != 0:
                Logger.print_warn(f"{name} preview failed (rc={rc})")
        input("\n按回车继续 ...")
