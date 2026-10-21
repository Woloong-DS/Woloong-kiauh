#!/bin/bash
# woloong-fork-sync —— 自有发行树（D20）的「重新叠加」工具
#
# 用途：把上游官方新版本吸收进我们的发行仓库，同时保证 woloong 定制不被破坏。
# 原理：上游树整体替换 -> 提交一个纯上游 commit -> 重放定制 -> 提交一个定制 commit（不做 merge）。
#
# 用法：woloong-fork-sync <发行仓库目录> --upstream-ref <ref> [--dry-run] [--tag <tag>] [--no-commit]
set -u

die() { echo "✗ $*" >&2; exit 1; }
info() { echo "  $*"; }

REPO="${1:-}"; [ -n "$REPO" ] || die "用法：woloong-fork-sync <发行仓库目录> --upstream-ref <ref> [--dry-run] [--tag <tag>]"
shift || true
REF=""; DRY=0; TAG=""; DO_COMMIT=1
while [ $# -gt 0 ]; do
  case "$1" in
    --upstream-ref) REF="${2:-}"; shift 2 ;;
    --dry-run)      DRY=1; shift ;;
    --tag)          TAG="${2:-}"; shift 2 ;;
    --no-commit)    DO_COMMIT=0; shift ;;
    *) die "未知参数：$1" ;;
  esac
done

cd "$REPO" || die "目录不存在：$REPO"
MAN="woloong-release"
[ -f "$MAN/assets.manifest.tsv" ] || die "这不是发行树（缺少 $MAN/assets.manifest.tsv）"
[ -d "$MAN/baseline" ] || die "缺少 $MAN/baseline（受控文件基线）"
[ -n "$REF" ] || die "必须指定 --upstream-ref"

# 行结尾必须是 LF（否则 Windows 下的检出会被转成 CRLF，导致定制校验整文件不一致）
git config core.autocrlf false
git config core.eol lf

echo "== woloong-fork-sync =="
info "仓库      : $(pwd)"
info "工作区脏数: $(git status --porcelain | wc -l)"
[ "$(git status --porcelain | wc -l)" -eq 0 ] || die "工作区不干净，请先提交或还原"

# 1) 抓取上游
git remote get-url upstream >/dev/null 2>&1 || die "未配置 upstream 远程（git remote add upstream <官方仓库>）"
git fetch -q --tags upstream || die "fetch upstream 失败"
UP_SHA="$(git rev-parse --verify "$REF^{commit}") " || die "无法解析 ref：$REF"
UP_SHA="$(echo "$UP_SHA" | tr -d ' ')"
UP_SHORT="$(echo "$UP_SHA" | cut -c1-8)"
info "上游 ref  : $REF = $UP_SHORT"

# 2) 基线漂移检测（受控文件是否被上游改动）
DRIFT=""
info "基线漂移检测："
while IFS= read -r b; do
  rel="${b#$MAN/baseline/}"
  if ! git cat-file -e "$UP_SHA:$rel" 2>/dev/null; then
    info "  ⚠ 上游已无此文件: $rel"; DRIFT="$DRIFT $rel"; continue
  fi
  tmp="$(mktemp)"
  git show "$UP_SHA:$rel" > "$tmp" 2>/dev/null
  if cmp -s "$b" "$tmp"; then info "  ✓ 基线未变: $rel"; else info "  ⚠ 上游已改动: $rel"; DRIFT="$DRIFT $rel"; fi
  rm -f "$tmp"
done < <(find "$MAN/baseline" -type f | sort)

if [ "$DRIFT" != "" ]; then
  echo ""
  echo "⚠ 基线漂移：以下受控文件的上游版本与我们的补丁基线不同"
  for d in $DRIFT; do echo "    - $d"; done
  echo "  处理方式（人工）：用新上游文件更新 $MAN/baseline/<path>，重新生成补丁（tools/make-patch.sh），并在本仓库提交后再重跑本工具。"
  [ "$DRY" -eq 1 ] || die "检测到基线漂移，已停止（未改动任何内容）"
fi

[ "$DRY" -eq 1 ] && { echo ""; echo "--dry-run：以上为检查结果，未改动任何内容。"; exit 0; }

# 3) 暂存定制：所有清单条目复制到仓库外的临时目录
STAGE="$(mktemp -d)"
info "暂存定制到 $STAGE"
count=0
while IFS=$'\t' read -r _sha rel; do
  [ -z "$rel" ] && continue
  if [ -f "$rel" ]; then mkdir -p "$STAGE/$(dirname "$rel")"; cp -p "$rel" "$STAGE/$rel"; count=$((count+1)); fi
done < <(tr -d '\r' < "$MAN/assets.manifest.tsv")
info "已暂存 $count 个定制文件"
cp -a "$MAN" "$STAGE/__man"
[ -f .gitattributes ] && cp -p .gitattributes "$STAGE/.gitattributes"

# 4) 上游树整体替换（保留 .git/）
info "用上游树替换工作区"
git rm -r --ignore-unmatch -q . || true
# 关键：先恢复 .gitattributes，使随后的检出按 eol=lf 写入（否则会被 CRLF 化）
if [ -f "$STAGE/.gitattributes" ]; then cp -p "$STAGE/.gitattributes" .gitattributes; info "已恢复 .gitattributes（LF 规则生效）"; fi
git checkout "$UP_SHA" -- . || die "从上游检出文件失败"
if [ "$DO_COMMIT" -eq 1 ]; then
  git -c user.email=ci@woloong.local -c user.name=Woloong commit -q -m "upstream: $(basename "$(git remote get-url upstream)" .git) @ $UP_SHORT" && info "已提交上游快照"
fi

# 4b) 恢复发行元数据目录（上游替换会删除它；补丁位于其中，必须先恢复）
info "恢复发行元数据目录"
rm -rf "$MAN"
cp -a "$STAGE/__man" "$MAN"

# 5) 重放定制：基线文件应用补丁，其余文件复制
info "重放 woloong 定制"
fail=0
while IFS= read -r b; do
  rel="${b#$MAN/baseline/}"
  p="$MAN/patches/$(echo "$rel" | tr '/' '_').patch"
  if [ ! -f "$p" ]; then info "  ⚠ 缺补丁，跳过：$rel（$p）"; fail=$((fail+1)); continue; fi
  if git apply "$p" 2>/dev/null; then info "  ✓ 补丁已应用: $rel"; else info "  ✗ 补丁应用失败: $rel"; fail=$((fail+1)); fi
done < <(find "$MAN/baseline" -type f | sort)
info "复制新增/资产文件"
if [ -d "$STAGE" ]; then
  ( cd "$STAGE" && find . -path ./__man -prune -o -type f -print ) | sed 's|^\./||' | while IFS= read -r rel; do
    case "$rel" in *__man*) continue ;; esac
    if [ -f "$MAN/baseline/$rel" ]; then continue; fi   # 受控文件已由补丁处理
    mkdir -p "$(dirname "$rel")"; cp -p "$STAGE/$rel" "$rel"
  done
fi
[ "$fail" -eq 0 ] || die "有 $fail 个补丁未能应用，请人工处理（工作区保留现场）"

# 6) 校验
echo ""
echo "== 定制校验 =="
# 5.5) 应用移除清单：上游有、但我们的发行版不要的文件/目录（否则每次重叠加都会复活它们）
if [ -f "$MAN/remove.list" ]; then
  info "应用移除清单 $MAN/remove.list"
  while IFS= read -r rp; do
    rp="$(printf '%s' "$rp" | tr -d '\r')"
    case "$rp" in ''|'#'*) continue ;; esac
    if [ -e "$rp" ]; then rm -rf "$rp"; info "  ✓ 已移除: $rp"; else info "  - 本就不存在: $rp"; fi
  done < "$MAN/remove.list"
fi
# 5.6) 记录本次吸收的上游基线（check-upstream 的审计依据）
if [ -n "${UP_SHA:-}" ] && [ -n "${REF:-}" ]; then
  REPO_URL="$(git remote get-url upstream 2>/dev/null || true)"
  REPO_SLUG="$(printf '%s' "$REPO_URL" | sed -E 's#.*github\.com[:/]##; s#\.git$##')"
  if [ -n "$REPO_SLUG" ]; then
    printf '{\n  "repo": "%s",\n  "base_ref": "%s",\n  "base_sha": "%s",\n  "note": "由 tools/fork-sync.sh 在重叠加成功后自动更新；tools/check-upstream.sh 据此审计是否遗漏上游发布。"\n}\n' \
      "$REPO_SLUG" "$REF" "$UP_SHA" > "$MAN/upstream.json"
    info "  ✓ 已更新基线声明 $MAN/upstream.json（$REF @ ${UP_SHA:0:8}）"
  fi
fi
bash "$MAN/tools/verify-assets.sh" || die "定制校验未通过（定制未完整重放）"

if [ "$DO_COMMIT" -eq 1 ]; then
  git add -A
  git -c user.email=ci@woloong.local -c user.name=Woloong commit -q -m "woloong: re-apply customization (upstream $UP_SHORT)" && info "已提交定制重放"
  if [ -n "$TAG" ]; then git -c user.email=ci@woloong.local -c user.name=Woloong tag -a "$TAG" -m "发行树：上游 $UP_SHORT + woloong 定制" && info "已打 tag：$TAG"; fi
  info "git describe: $(git describe --always --tags --long --dirty)"
  info "工作区脏数: $(git status --porcelain | wc -l)"
fi
rm -rf "$STAGE"
echo "✅ 完成"
