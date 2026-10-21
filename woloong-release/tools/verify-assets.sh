#!/bin/bash
# 按 assets.manifest.tsv 校验工作区中的 woloong 定制文件是否完整
set -u
cd "$(dirname "$0")/.." || exit 1
root="$(cd .. && pwd)"
fail=0; ok=0
while IFS=$'\t' read -r sha rel; do
  [ -z "${sha:-}" ] && continue
  f="$root/$rel"
  if [ ! -f "$f" ]; then echo "  MISSING  $rel"; fail=$((fail+1)); continue; fi
  got=$(sha256sum "$f" | cut -c1-64)
  if [ "$got" = "$sha" ]; then ok=$((ok+1)); else echo "  MISMATCH $rel"; fail=$((fail+1)); fi
done < <(tr -d '\r' < assets.manifest.tsv)
# 额外断言：移除清单中的文件必须**不存在**（防止重叠加把上游 CI/dependabot 带回来）
#   注意：脚本已 cd 到 woloong-release/，仓库根为 $root；remove.list 中的路径均相对仓库根。
if [ -f "remove.list" ]; then
  while IFS= read -r rp; do
    rp="$(printf '%s' "$rp" | tr -d '\r')"
    case "$rp" in ''|'#'*) continue ;; esac
    if [ -e "$root/$rp" ]; then echo "  [FAIL] 应被移除但仍存在: $rp"; fail=$((fail+1)); fi
  done < remove.list
fi

echo "verify-assets: ok=$ok fail=$fail"
[ "$fail" -eq 0 ] || exit 1
exit 0
