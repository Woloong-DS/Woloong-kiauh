#!/bin/bash
# ============================================================================
# test-capability.sh —— Woloong-kiauh 的**产品能力**验证（C1–C7 ✓）
#
# 用户判据（2026-10-21）：
#   「Woloong-kiauh 是安装器：安装 / 管理 / 卸载 base 软件」
#   「不能只验界面文案 ✗ —— 要验能力可达 ✓」
#
# 注意：本测试**只验「可达性/结构」** ✓
#      不在 CI/验证机上真装真卸（那是设备验收的事 ✓）
# ============================================================================
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT" || exit 1
P=0; F=0
ok(){ printf "  [PASS] %s\n" "$1"; P=$((P+1)); }
bad(){ printf "  [FAIL] %s\n" "$1"; F=$((F+1)); }
echo '============================================================'
echo 'Woloong-kiauh 产品能力验证（C1–C7）'
echo '============================================================'

# ---- C1 主菜单 10 个入口（从源码读 ✓ 不写死 ✗）----
MAIN=kiauh/core/menus/main_menu.py
if [ -f "$MAIN" ]; then
  MISS=""
  for e in Install Remove Update Advanced Backup Settings; do
    grep -qF "[$e]" "$MAIN" 2>/dev/null || MISS="$MISS $e"
  done
  if [ -z "$MISS" ]; then ok "C1 主菜单入口齐全（Install/Remove/Update/Advanced/Backup/Settings ✓）"
  else bad "C1 主菜单缺入口:$MISS ✗"; fi
  for e in Extension Log-Upload; do
    grep -qF "$e" "$MAIN" 2>/dev/null && ok "C1 主菜单含 $e ✓" || bad "C1 主菜单缺 $e ✗"
  done
else bad "C1 缺 main_menu.py ✗"; fi

# ---- C2 组件菜单可导入（6 个 ✓）----
if command -v python3 >/dev/null 2>&1; then
  _c2=$(PYTHONPATH="$ROOT" python3 - <<'PY2' 2>&1
import importlib, sys
mods = [
    'kiauh.components.klipper.menus.klipper_remove_menu',
    'kiauh.components.moonraker.menus.moonraker_remove_menu',
    'kiauh.components.webui_client.menus.client_install_menu',
    'kiauh.components.webui_client.menus.client_remove_menu',
    'kiauh.components.klipper_firmware.menus.klipper_build_menu',
    'kiauh.components.klipper_firmware.menus.klipper_flash_menu',
]
bad = []
for m in mods:
    try:
        importlib.import_module(m)
    except Exception as e:
        bad.append('%s(%s)' % (m.split('.')[-1], type(e).__name__))
print('OK' if not bad else 'FAIL:' + ','.join(bad))
PY2
  )
  [ "$_c2" = "OK" ] && ok "C2 6 个组件菜单全部可导入 ✓" || bad "C2 组件菜单导入失败：$_c2 ✗"
fi

# ---- C3 4 个 setup service 可实例化 + install/remove/update 齐备 ----
if command -v python3 >/dev/null 2>&1; then
  _c3=$(PYTHONPATH="$ROOT" python3 - <<'PY3' 2>&1
import inspect, importlib
specs = [
    ('kiauh.components.klipper.services.klipper_setup_service', 'KlipperSetupService'),
    ('kiauh.components.moonraker.services.moonraker_setup_service', 'MoonrakerSetupService'),
    ('kiauh.components.webui_client.services.web_client_setup_service', 'WebClientSetupService'),
    ('kiauh.components.webui_client.services.web_client_config_setup_service', 'WebClientConfigSetupService'),
]
bad = []
for mod, cls in specs:
    try:
        m = importlib.import_module(mod)
        c = getattr(m, cls)
        has = all(hasattr(c, f) for f in ('install', 'remove', 'update'))
        if not has: bad.append(cls + ':缺install/remove/update')
    except Exception as e:
        bad.append(cls + '(%s)' % type(e).__name__)
print('OK' if not bad else 'FAIL:' + ';'.join(bad))
PY3
  )
  [ "$_c3" = "OK" ] && ok "C3 4 个 setup service 可导入且 install/remove/update 齐备 ✓" || bad "C3 service 能力缺失：$_c3 ✗"
fi

# ---- C4 W) 4 档 dry-run（结构 ✓ + 安装器可调用 ✓）----
if command -v python3 >/dev/null 2>&1; then
  _c4=$(PYTHONPATH="$ROOT" python3 - <<'PY4' 2>&1
try:
    import kiauh.core.menus.woloong_menu as m
    names = [n for n in dir(m) if 'TIER' in n.upper()]
    v = getattr(m, names[0]) if names else None
    ks = sorted(v.keys()) if isinstance(v, dict) else []
    print('OK:' + ','.join(ks) if len(ks) >= 4 else 'FAIL:只有%d档' % len(ks))
except Exception as e:
    print('ERR:%s' % type(e).__name__)
PY4
  )
  case "$_c4" in
    OK:*) ok "C4 W) 预置包 $_c4" ;;
    *) bad "C4 预置包异常：$_c4 ✗" ;;
  esac
fi
# 安装器**调用关系**（安装器本体在 Woloong-OS/install/ ✓ 不在本仓库 ✗）
if grep -q "woloong-base-install" kiauh/core/menus/woloong_menu.py 2>/dev/null; then
  ok "C4 woloong_menu 调用 woloong-base-install ✓"
else bad "C4 woloong_menu 未调用安装器 ✗"; fi
if grep -qE "\-\-tier" kiauh/core/menus/woloong_menu.py 2>/dev/null; then
  ok "C4 按 --tier 传档位 ✓"
else bad "C4 缺 --tier 传参 ✗"; fi
if grep -qi "dry" kiauh/core/menus/woloong_menu.py 2>/dev/null; then
  ok "C4 含 dry-run 预览 ✓"
else bad "C4 缺 dry-run ✗"; fi

# ---- C5 卸载流程可达 ----
if [ -f kiauh/core/menus/remove_menu.py ]; then ok "C5 remove_menu.py 存在 ✓"; else bad "C5 缺 remove_menu.py ✗"; fi
for f in kiauh/components/klipper/menus/klipper_remove_menu.py kiauh/components/moonraker/menus/moonraker_remove_menu.py kiauh/components/webui_client/menus/client_remove_menu.py; do
  [ -f "$f" ] && ok "C5 $(basename $f) 存在 ✓" || bad "C5 缺 $(basename $f) ✗"
done

# ---- C6 更新流程可达 ----
if [ -f kiauh/core/menus/update_menu.py ]; then ok "C6 update_menu.py 存在 ✓"; else bad "C6 缺 update_menu.py ✗"; fi
grep -q "def update" kiauh/components/klipper/services/klipper_setup_service.py 2>/dev/null && ok "C6 klipper 有 update ✓" || bad "C6 klipper 缺 update ✗"
grep -q "def update" kiauh/components/moonraker/services/moonraker_setup_service.py 2>/dev/null && ok "C6 moonraker 有 update ✓" || bad "C6 moonraker 缺 update ✗"

# ---- C7 备份 / 日志上传 / 固件 ----
for pair in "kiauh/core/menus/backup_menu.py:备份" "kiauh/core/services/backup_service.py:备份服务" "kiauh/components/log_uploads/menus/log_upload_menu.py:日志上传" "kiauh/components/klipper_firmware/menus/klipper_build_menu.py:固件编译" "kiauh/components/klipper_firmware/menus/klipper_flash_menu.py:固件烧写" "kiauh/extensions/extensions_menu.py:扩展"; do
  f="${pair%%:*}"; n="${pair##*:}"
  [ -f "$f" ] && ok "C7 $n 可达 ✓" || bad "C7 缺 $n（$f）✗"
done

echo '============================================================'
printf "  能力验证汇总：PASS=%s FAIL=%s\n" "$P" "$F"
[ "$F" -eq 0 ] && echo "  ★ CAPABILITY_OK —— 产品能力可达性全部通过 ✓" && exit 0
echo "  ★ CAPABILITY_FAILED ✗"
exit 1
