#!/bin/bash
# 重新生成全部受控文件补丁（基线 vs 当前工作区）
# 使用 a/ b/ 前缀标签，保证 git apply（默认 -p1）可直接应用
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p patches
find baseline -type f | sort | while IFS= read -r b; do
  rel="${b#baseline/}"
  out="patches/$(echo "$rel" | tr '/' '_').patch"
  diff -u --label "a/$rel" --label "b/$rel" "$b" "../$rel" > "$out" || true
  echo "  $rel -> $(basename "$out") ($(wc -l < "$out") 行)"
done
