#!/bin/bash
# ============================================================================
# test-customization.sh —— Woloong-kiauh 定制功能测试（**仓库级** ✓ 不需要镜像 ✗）
#
# 用户判据（2026-10-21）：
#   「Woloong-kiauh = kiauh + Woloong 定制数据」
#   → 定制功能必须在**仓库层**可测 ✓，不能靠烧录镜像才知道 ✗
#
# 用法：bash tests/test-customization.sh   （在仓库根目录或任意位置 ✓）
# ============================================================================
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT" || exit 1
P=0; F=0
ok(){ printf "  [PASS] %s\n" "$1"; P=$((P+1)); }
bad(){ printf "  [FAIL] %s\n" "$1"; F=$((F+1)); }
echo '============================================================'
echo 'Woloong-kiauh 定制功能测试'
echo '============================================================'

# ---- T1 安装菜单改名 ----
M=kiauh/core/menus/install_menu.py
grep -q "W) \[Woloong Preset Bundles\]" "$M" 2>/dev/null && ok "T1 安装菜单有 W) 预置包入口 ✓" || bad "T1 缺 W) 预置包入口 ✗"
# 注：按 P45 设计，上游单项已被 W) 预置包取代 ✗ -> 改名由 T3/T4 在组件层验证 ✓
grep -q "已剔除" "$M" 2>/dev/null && ok "T1 菜单已声明剔除上游 Mainsail/KlipperScreen ✓" || bad "T1 菜单未声明剔除 ✗"
grep -qE "^\s*[0-9]+\) \[Mainsail\]" "$M" 2>/dev/null && bad "T1 仍有上游 [Mainsail] 安装项 ✗" || ok "T1 无上游 [Mainsail] 安装项 ✓"
grep -qE "^\s*[0-9]+\) \[KlipperScreen\]" "$M" 2>/dev/null && bad "T1 仍有上游 [KlipperScreen] 安装项 ✗" || ok "T1 无上游 [KlipperScreen] 安装项 ✓"

# ---- T2 主菜单移除 W) ----
MM=kiauh/core/menus/main_menu.py
grep -q "W) \[Woloong\]" "$MM" 2>/dev/null && bad "T2 主菜单仍有 W)（应已迁入安装菜单 ✗）" || ok "T2 主菜单已移除 W) ✓"

# ---- T3 KlipperScreen 指向 fork ----
KS=kiauh/components/klipperscreen/__init__.py
grep -q "Woloong-DS/Woloong-klipperScreen.git" "$KS" 2>/dev/null && ok "T3 KlipperScreen 指向 Woloong fork ✓" || bad "T3 KlipperScreen 仍指上游 ✗"
grep -qE 'KLIPPERSCREEN_DIR = Path\.home\(\)\.joinpath\("woloong-klipperScreen"\)' "$KS" 2>/dev/null && ok "T3 产品目录 = ~/woloong-klipperScreen ✓" || bad "T3 产品目录未去重 ✗"

# ---- T4 Mainsail 显示名 + 目录 ----
MD=kiauh/components/webui_client/mainsail_data.py
grep -q "Woloong Mainsail" "$MD" 2>/dev/null && ok "T4 Mainsail 显示名 = Woloong Mainsail ✓" || bad "T4 Mainsail 显示名未改 ✗"
grep -qE 'client_dir: Path = Path\.home\(\)\.joinpath\("woloong-mainsail"\)' "$MD" 2>/dev/null && ok "T4 Mainsail 目录 = ~/woloong-mainsail ✓" || bad "T4 Mainsail 目录未去重 ✗"

# ---- T5 离线克隆注入（函数级 ✓ 比 grep 文件级更严 ✓）----
if command -v python3 >/dev/null 2>&1; then
  _r=$(PYTHONPATH="$ROOT" python3 - <<'PYFN' 2>&1
import inspect, sys
try:
    from kiauh.utils import git_utils, sys_utils
    a = "_woloong_offline_clone" in inspect.getsource(git_utils.git_clone_wrapper)
    b = "_woloong_offline_url" in inspect.getsource(sys_utils.download_file)
    print("OK" if (a and b) else "MISS:%s%s" % ("" if a else "clone ", "" if b else "download"))
except Exception as e:
    print("ERR:%s" % type(e).__name__)
PYFN
  )
  [ "$_r" = "OK" ] && ok "T5 离线注入在函数内部 ✓" || bad "T5 离线注入不在函数内：$_r ✗"
else
  warn "T5 跳过（无 python3）"
fi

# ---- T6 档位菜单可构造 + 4 档 ----
if command -v python3 >/dev/null 2>&1; then
  _t=$(PYTHONPATH="$ROOT" python3 - <<'PYT' 2>&1
import sys
try:
    from kiauh.core.menus.woloong_menu import WOLOONG_TIERS
    print(",".join(sorted(WOLOONG_TIERS.keys())))
except Exception:
    try:
        import kiauh.core.menus.woloong_menu as m
        names = [n for n in dir(m) if "TIER" in n.upper()]
        v = getattr(m, names[0]) if names else None
        print(",".join(sorted(v.keys())) if isinstance(v, dict) else "NODICT")
    except Exception as e:
        print("ERR:%s" % type(e).__name__)
PYT
  )
  case "$_t" in
    *mono_basic*) ok "T6 档位菜单可构造：$_t ✓" ;;
    *) bad "T6 档位菜单不可构造或档位缺失：$_t ✗" ;;
  esac
fi

# ---- T7 ASCII 框等宽 ----
if command -v python3 >/dev/null 2>&1; then
  _w=$(python3 - "$M" <<'PYW' 2>&1
import sys
BOX = ("\u2551", "\u255f", "\u255a", "\u2554", "\u2560", "\u255e", "\u2561", "\u2564", "\u2567")
art = [l.strip() for l in open(sys.argv[1], encoding="utf-8", errors="replace").read().splitlines() if l.strip().startswith(BOX)]
print(",".join(str(x) for x in sorted(set(len(l) for l in art))) if art else "NONE")
PYW
  )
  case "$_w" in
    NONE) bad "T7 未找到 ASCII 框 ✗" ;;
    *,*) bad "T7 框宽不一致：$_w ✗" ;;
    *) ok "T7 ASCII 框等宽（$_w）✓" ;;
  esac
fi

# ---- T8 事务接线 ----
grep -q "woloong-base-install" kiauh/core/menus/woloong_menu.py 2>/dev/null && ok "T8 档位菜单接 Woloong 安装器 ✓" || bad "T8 未接安装器 ✗"
grep -q "\-\-tier" kiauh/core/menus/woloong_menu.py 2>/dev/null && ok "T8 按 --tier 传参 ✓" || bad "T8 缺 --tier ✗"
grep -qi "dry" kiauh/core/menus/woloong_menu.py 2>/dev/null && ok "T8 含 dry-run ✓" || bad "T8 缺 dry-run ✗"

# ---- T9 原有组件保留 ----
_n=$(ls kiauh/components 2>/dev/null | wc -l)
[ "$_n" -ge 9 ] && ok "T9 原有组件保留（$_n 个）✓" || bad "T9 组件缺失（$_n 个 < 9 ✗）"

# ---- T10 定制资产完整（调 verify-assets ✓）----
if [ -x woloong-release/tools/verify-assets.sh ]; then
  _v=$(bash woloong-release/tools/verify-assets.sh 2>&1 | tail -1)
  case "$_v" in
    *"fail=0"*) ok "T10 定制资产完整（$_v）✓" ;;
    *) bad "T10 定制资产不完整（$_v）✗" ;;
  esac
fi

echo '============================================================'
printf "  测试汇总：PASS=%s FAIL=%s\n" "$P" "$F"
[ "$F" -eq 0 ] && echo "  ★ CUSTOMIZATION_OK —— 定制功能全部通过 ✓" && exit 0
echo "  ★ CUSTOMIZATION_FAILED ✗"
exit 1
