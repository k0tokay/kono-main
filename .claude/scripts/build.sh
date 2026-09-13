#!/bin/bash
# 『詳説』全体ビルド．成功時にスタンプを書く（precommit-check.py が参照）．
# 使い方: .claude/scripts/build.sh [--full] [chapter.tex]
#   --full      lualatex → bibtex → lualatex ×2 で参照と文献まで解決する（時間がかかる）．既定は lualatex 1回．
#   chapter.tex 章の単独ビルドも行う（スタンプは全体ビルド時のみ）．
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
STAMPDIR="$ROOT/local/build-artifacts"; mkdir -p "$STAMPDIR"
STAMP="$STAMPDIR/detail-build.ok"
FULL=0; if [ "${1:-}" = "--full" ]; then FULL=1; shift; fi
if [ -n "${1:-}" ]; then
  CH="$1"; DIR=$(dirname "$CH"); BASE=$(basename "$CH")
  ( cd "$ROOT/$DIR" && lualatex -interaction=nonstopmode -halt-on-error "$BASE" >/dev/null 2>&1 )
  if [ $? -ne 0 ]; then echo "[build] 章単独ビルド失敗: $CH"; grep -n -A3 '^!' "$ROOT/$DIR/${BASE%.tex}.log" | head -30; exit 1; fi
  echo "[build] 章単独ビルド成功: $CH"
fi
cd "$ROOT/detail" || exit 1
rm -f "$STAMP"
lualatex -interaction=nonstopmode -halt-on-error main-detail.tex >/dev/null 2>&1
RC=$?
if [ $RC -eq 0 ] && [ $FULL -eq 1 ]; then
  bibtex main-detail >/dev/null 2>&1
  lualatex -interaction=nonstopmode -halt-on-error main-detail.tex >/dev/null 2>&1
  lualatex -interaction=nonstopmode -halt-on-error main-detail.tex >/dev/null 2>&1
  RC=$?
fi
if [ $RC -ne 0 ]; then
  echo "[build] 全体ビルド失敗（exit $RC）．エラー:"
  grep -n -A3 '^!' main-detail.log | head -40
  exit 1
fi
UNDEF=$(grep -c "Reference .* undefined\|Citation .* undefined" main-detail.log)
MULTI=$(grep -c "multiply defined" main-detail.log)
echo "$(date '+%F %T') $(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null) undefined=$UNDEF multiply-defined=$MULTI" > "$STAMP"
MODE=quick; [ $FULL -eq 1 ] && MODE=full
echo "[build] 全体ビルド成功（$MODE）． $(cat "$STAMP")"
if [ "$UNDEF" != "0" ] || [ "$MULTI" != "0" ]; then
  echo "[build] 参照の警告があります（undefined=$UNDEF, multiply-defined=$MULTI）．--full で解消する場合があります："
  grep "Reference .* undefined\|Citation .* undefined\|multiply defined" main-detail.log | sort -u | head -10
fi
