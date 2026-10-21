#!/bin/bash
# ============================================================================
# check-upstream.sh —— 审计「我们的发行树」与「上游发布」的对应关系
#   判定：woloong-release/upstream.json 里的 base_ref 是否等于上游最新 tag
#   若落后：**逐一列出所有未吸收的上游版本**（不遗漏任何一个），退出码 1
# 用法: bash woloong-release/tools/check-upstream.sh
# ============================================================================
set -u
cd "$(dirname "$0")/.." || exit 1        # → woloong-release/
root="$(cd .. && pwd)"
J="upstream.json"
[ -f "$J" ] || { echo "[FAIL] 缺少 $J（基线声明）"; exit 2; }
REPO=$(python3 -c "import json;print(json.load(open('$J',encoding='utf-8'))['repo'])")
BASE=$(python3 -c "import json;print(json.load(open('$J',encoding='utf-8'))['base_ref'])")
BASESHA=$(python3 -c "import json;print(json.load(open('$J',encoding='utf-8')).get('base_sha',''))")
git -C "$root" remote get-url upstream >/dev/null 2>&1 || git -C "$root" remote add upstream "https://github.com/$REPO.git"
git -C "$root" fetch -q --tags upstream || { echo "[FAIL] 无法抓取上游 $REPO"; exit 2; }
TAGS=$(git -C "$root" tag --sort=-creatordate | grep -v '^woloong-')
LATEST=$(printf '%s\n' "$TAGS" | head -1)
echo "上游仓库 : $REPO"
echo "我们的基线: $BASE  ($BASESHA)"
echo "上游最新  : $LATEST"
if [ -z "$LATEST" ]; then echo '[WARN] 上游没有任何 tag（可能改用分支发布）'; exit 1; fi
if [ "$BASE" = "$LATEST" ]; then
  echo '[OK] 我们的发行树已对应上游最新发布 ✓'
  exit 0
fi
MISSED=$(printf '%s\n' "$TAGS" | awk -v base="$BASE" '$0==base{exit} {print}')
N=$(printf '%s\n' "$MISSED" | grep -c . || true)
echo "[BEHIND] 落后上游，未吸收的版本共 $N 个（逐一列出，确保不遗漏）:"
printf '%s\n' "$MISSED" | sed 's/^/  - /'
echo "处理：跑 upstream-sync 工作流（或本地 fork-sync）吸收到 $LATEST"
exit 1
