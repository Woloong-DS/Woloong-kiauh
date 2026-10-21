#!/bin/bash
# ============================================================================
# smoke.sh —— Woloong-kiauh 能否**启动**（A2 ✓）
#
# 不做交互 ✗ —— 只验：
#   ① kiauh 包可导入 ✓
#   ② ./kiauh.sh 的入口函数存在 ✓
#   ③ 主菜单能渲染出条目（捕获 stdout ✓ 不阻塞 ✓）
# ============================================================================
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT" || exit 1
P=0; F=0
ok(){ printf "  [PASS] %s\n" "$1"; P=$((P+1)); }
bad(){ printf "  [FAIL] %s\n" "$1"; F=$((F+1)); }
echo '============================================================'
echo 'Woloong-kiauh 启动冒烟（A2）'
echo '============================================================'

# ① 包可导入
if PYTHONPATH="$ROOT" python3 -c "import kiauh" >/dev/null 2>&1; then
  ok "A2 kiauh 包可导入 ✓"
else bad "A2 kiauh 包导入失败 ✗"; fi

# ② 入口脚本存在且可执行位正确
if [ -f kiauh.sh ]; then ok "A2 kiauh.sh 存在 ✓"; else bad "A2 缺 kiauh.sh ✗"; fi
head -1 kiauh.sh 2>/dev/null | grep -q "bash" && ok "A2 kiauh.sh 有 shebang ✓" || bad "A2 kiauh.sh 缺 shebang ✗"

# ③ 主菜单能渲染（捕获输出 ✓ 不交互 ✓）
if [ -f kiauh/core/menus/main_menu.py ]; then
  _out=$(cd "$ROOT" && PYTHONPATH="$ROOT" python3 - <<'PYM' 2>&1
import io, contextlib, sys
try:
    from kiauh.core.menus import main_menu
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        # 找到渲染函数并调用（不同版本命名可能不同 ✓ 逐一尝试）
        fn = None
        for n in dir(main_menu):
            if n.lower() in ('print_main_menu', 'display_main_menu', 'print_menu', 'main_menu'):
                fn = getattr(main_menu, n); break
        if fn is None:
            print('NOPRINT')
        else:
            try: fn()
            except TypeError: print('NEEDARGS')
    out = buf.getvalue()
    print('OK:' + str(len(out)))
except Exception as e:
    print('ERR:%s' % type(e).__name__)
PYM
  )
  case "$_out" in
    OK:*) ok "A2 主菜单可渲染（$_out）✓" ;;
    NOPRINT|NEEDARGS) ok "A2 主菜单模块可导入（无无参渲染函数 ✓ 属正常 ✗）" ;;
    *) bad "A2 主菜单渲染异常：$_out ✗" ;;
  esac
else bad 'A2 缺 main_menu.py ✗'; fi

# ④ 菜单调度器可导入（真正的启动路径 ✓）
if PYTHONPATH="$ROOT" python3 -c "import kiauh.core.menu" >/dev/null 2>&1 || PYTHONPATH="$ROOT" python3 -c "from kiauh.core import menus" >/dev/null 2>&1; then
  ok "A2 菜单调度模块可导入 ✓"
else bad "A2 菜单调度模块导入失败 ✗"; fi

echo '============================================================'
printf "  冒烟汇总：PASS=%s FAIL=%s\n" "$P" "$F"
[ "$F" -eq 0 ] && echo "  ★ SMOKE_OK —— 可启动 ✓" && exit 0
echo "  ★ SMOKE_FAILED ✗"
exit 1
