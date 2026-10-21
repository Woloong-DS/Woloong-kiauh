#!/bin/bash
# ============================================================================
# audit-upstream.sh —— Woloong-kiauh 是否**保留了上游全部原有功能**（A1 ✓）
#
# 做法：
#   · 用 upstream.json 的 base_sha 从 git 展开**上游全树** ✓
#   · 抽取上游每个 .py 的顶层 def/class 与方法 ✓
#   · 逐一确认我们的树里仍然存在 ✓
#
# 输出：UPSTREAM_AUDIT files=N symbols=M missing=K
# 用法：bash woloong-release/tools/audit-upstream.sh
# ============================================================================
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1        # -> woloong-release/
REL="$(cd .. && pwd)"
[ -f upstream.json ] || { echo "[FAIL] 缺 upstream.json ✗"; exit 2; }
BASE_SHA=$(python3 -c "import json;print(json.load(open('upstream.json',encoding='utf-8'))['base_sha'])" 2>/dev/null)
[ -n "$BASE_SHA" ] || { echo "[FAIL] upstream.json 缺 base_sha ✗"; exit 2; }
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
if ! git -C "$REL" archive "$BASE_SHA" 2>/dev/null | tar -x -C "$TMP" 2>/dev/null; then
  echo "[FAIL] 无法从 $BASE_SHA 展开上游树 ✗（先 git fetch upstream --tags ✓）"; exit 2
fi
echo "上游基线: $BASE_SHA（展开到 $TMP ✓）"
python3 - "$TMP" "$REL" <<'PYAUDIT'
import sys, pathlib
up = pathlib.Path(sys.argv[1])
ours = pathlib.Path(sys.argv[2])
def walk(d):
    return [p for p in d.rglob('*.py') if '__pycache__' not in p.parts and '/tests/' not in str(p) and not p.name.startswith('test_')]
def syms(p):
    out = []
    for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
        s = line.rstrip()
        if s.startswith(('def ', 'class ')):
            out.append(s.split('(')[0].split(':')[0].strip())
        elif s.startswith('    def '):
            out.append('.' + s.strip().split('(')[0])
    return out
files = walk(up)
missing, checked, total = [], 0, 0
for f in files:
    rel = f.relative_to(up)
    checked += 1
    tgt = ours / rel
    if not tgt.exists():
        missing.append('%s missing entirely' % rel)
        continue
    have = set(syms(tgt))
    for s in syms(f):
        total += 1
        if s not in have:
            missing.append('%s :: %s' % (rel, s))
print('UPSTREAM_AUDIT files=%d symbols=%d missing=%d' % (checked, total, len(missing)))
for m in missing[:30]:
    print('  MISSING ' + m)
sys.exit(1 if missing else 0)
PYAUDIT
