#!/usr/bin/env python3
# ============================================================================
# test-parity.py —— TUI 与 CLI 的「动作 × 组件」必须对齐（防漂移 ✗）
#
# 事故背景（2026-10-22）：
#   · TUI 可装 crowsnest 但 CLI 装不了 ✗
#   · TUI 可卸 klipperscreen/crowsnest 但 CLI 卸不了 ✗
#   · 配置类（mainsail-config/fluidd-config）**可装不可卸** ✗
#   → 功能没闭环，用户在不同入口体验不一致 ✗
#
# 判据：
#   1) 每个组件的 install/remove/update 在 TUI 与 CLI 都要有（去重例外见 EXCEPTIONS）
#   2) 可装必须可卸（含配置类）
#   3) 例外必须显式登记理由（不许静默 ✗）
# ============================================================================
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MENUS = ROOT / "kiauh" / "core" / "menus"
CLI = ROOT / "kiauh" / "core" / "cli" / "__init__.py"

# 去重设计（P45）：上游 [Mainsail] / [KlipperScreen] 安装入口已剔除，
# 由安装菜单 w) [Woloong Preset Bundles] 提供 Woloong 版 ✓
# 但「卸载」必须保留（用于清理上游同名残留 ✓）
EXCEPTIONS = {
    ("install", "mainsail"): "P45 去重：安装由 W) 预置包提供 Woloong-mainsail ✓",
    ("install", "klipperscreen"): "P45 去重：安装由 W) 预置包提供 Woloong-klipperScreen ✓",
    ("remove", "mainsail"): "保留：用于清理上游 mainsail 残留 ✓",
    ("remove", "klipperscreen"): "保留：用于清理上游 KlipperScreen 残留 ✓",
}


def tui_actions(action: str) -> set:
    f = MENUS / ("%s_menu.py" % action)
    if not f.exists():
        return set()
    src = f.read_text(encoding="utf-8")
    return set(re.findall(r"self\.%s_([a-z_]+)\b" % action, src))


def cli_actions(action: str) -> set:
    sys.path.insert(0, str(ROOT))
    from kiauh.core.cli import DISPATCH  # noqa: WPS433

    return {c for (a, c) in DISPATCH.keys() if a == action}


def norm(x: str) -> str:
    return x.replace("_", "-")


P = F = 0


def ok(msg):
    global P
    P += 1
    print("  [PASS] " + msg)


def bad(msg):
    global F
    F += 1
    print("  [FAIL] " + msg)


print("=" * 78)
print("TUI 与 CLI 动作对齐（parity）")
print("=" * 78)

for action in ("install", "remove", "update"):
    tui = {norm(x) for x in tui_actions(action) if x not in ("all", "presets")}
    cli = {norm(x) for x in cli_actions(action)}
    only_tui = sorted(tui - cli)
    only_cli = sorted(cli - tui)
    print("\n[%s]  TUI=%d  CLI=%d" % (action, len(tui), len(cli)))

    for c in only_tui:
        key = (action, c)
        if key in EXCEPTIONS:
            ok("%-16s 仅 TUI（已登记例外：%s）" % (c, EXCEPTIONS[key]))
        else:
            bad("%-16s 仅 TUI 有、CLI 缺 ✗（请补 CLI 或登记例外）" % c)
    for c in only_cli:
        key = (action, c)
        if key in EXCEPTIONS:
            ok("%-16s 仅 CLI（已登记例外：%s）" % (c, EXCEPTIONS[key]))
        else:
            bad("%-16s 仅 CLI 有、TUI 缺 ✗" % c)
    if not only_tui and not only_cli:
        ok("完全对齐（%d 项）" % len(tui))

# 可装必可卸（含配置类）
print("\n[可装必须可卸]")
inst = {norm(x) for x in tui_actions("install") if x not in ("all", "presets")} | {
    norm(x) for x in cli_actions("install")
}
rem = {norm(x) for x in tui_actions("remove")} | {norm(x) for x in cli_actions("remove")}
no_rm = sorted(inst - rem)
if no_rm:
    for c in no_rm:
        bad("%-16s 可装但不可卸 ✗" % c)
else:
    ok("所有可装组件都有卸载入口 ✓（%d 项）" % len(inst))

# 可装必可更新
print("\n[可装必须可更新]")
upd = {norm(x) for x in tui_actions("update")} | {norm(x) for x in cli_actions("update")}
no_up = sorted(inst - upd)
if no_up:
    for c in no_up:
        bad("%-16s 可装但不可更新 ✗" % c)
else:
    ok("所有可装组件都有更新入口 ✓")

print("=" * 78)
print("汇总：PASS=%d FAIL=%d" % (P, F))
print("PARITY_OK — TUI 与 CLI 已对齐 ✓" if F == 0 else "PARITY_FAILED ✗")
sys.exit(1 if F else 0)
