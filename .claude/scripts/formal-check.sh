#!/bin/bash
# 形式検査：機械で判定できるものだけを検査する（ビルド・lint・辞書validate・テスト・ハーネス構文）．
# 理論の質は判定しない．コミット前に通す（precommit-check.py が要求）．
# 使い方: .claude/scripts/formal-check.sh [--full]      --full は build.sh --full（bibtex 込み）
# 判定対象は「HEAD との差分がある領域」だけ．全部通れば local/build-artifacts/formal-check.ok を書く．
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$ROOT" || exit 1
STAMPDIR="local/build-artifacts"; mkdir -p "$STAMPDIR"; STAMP="$STAMPDIR/formal-check.ok"; rm -f "$STAMP"
FULL=""; [ "${1:-}" = "--full" ] && FULL="--full"
CHANGED=$( { git diff --name-only HEAD; git diff --name-only --cached; git ls-files --others --exclude-standard; } | sort -u )
FAIL=0; RESULTS=()
note(){ RESULTS+=("$1"); echo "$1"; }
run(){ # run <名前> <コマンド...>
  local name="$1"; shift
  if "$@" > "$STAMPDIR/gate-$name.log" 2>&1; then note "PASS $name"; else FAIL=1; note "FAIL $name  （$STAMPDIR/gate-$name.log）"; tail -15 "$STAMPDIR/gate-$name.log" | sed 's/^/    /'; fi
}
# 1. 本文 .tex：ビルド＋lint
if echo "$CHANGED" | grep -qE '^detail/.*\.tex$'; then
  run detail-build bash .claude/scripts/build.sh $FULL
  LINT=0
  for f in $(echo "$CHANGED" | grep -E '^detail/chapters/.*\.tex$'); do
    [ -f "$f" ] || continue
    out=$(printf '{"tool_name":"Write","tool_input":{"file_path":"%s"}}' "$ROOT/$f" | python3 .claude/scripts/tex-lint.py)
    if [ -n "$out" ]; then LINT=1; python3 -c "import json,sys;print(json.load(sys.stdin)['hookSpecificOutput']['additionalContext'])" <<<"$out" | sed 's/^/    /'; fi
  done
  if [ $LINT -eq 0 ]; then note "PASS tex-lint"; else note "WARN tex-lint（文体の機械検査に指摘あり．拒否はしない．内容を確認する）"; fi
  run issues-sync python3 detail/scripts/issues.py sync
  run detail-scripts-tests bash -c 'cd detail/scripts && python3 -m unittest -q test_appline_patterns'
else
  note "SKIP detail（.tex の変更なし）"
fi
# 2. 辞書
if echo "$CHANGED" | grep -qE '^kono-dictionary-editor/'; then
  run dict-validate bash -c 'cd kono-dictionary-editor && npm run --silent dict -- validate | python3 -c "import json,sys;d=json.load(sys.stdin);sys.exit(0 if d.get(\"ok\") else 1)"'
  if echo "$CHANGED" | grep -qE '^kono-dictionary-editor/(bin|src|test)/.*\.(js|mjs|jsx|ts|tsx)$'; then
    run dict-tests bash -c 'cd kono-dictionary-editor && npm test --silent'
  fi
else
  note "SKIP dictionary（変更なし）"
fi
# 3. 音韻
if echo "$CHANGED" | grep -qE '^kono-phonology/'; then
  run phonology-tests bash -c 'cd kono-phonology && python3 -m unittest discover -q -s tests'
else
  note "SKIP phonology（変更なし）"
fi
# 4. ハーネス自身
if echo "$CHANGED" | grep -qE '^\.claude/'; then
  run harness-settings python3 -c "import json;json.load(open('.claude/settings.json'))"
  run harness-scripts bash -c 'for f in .claude/scripts/*.sh; do bash -n "$f" || exit 1; done; for f in .claude/scripts/*.py; do python3 -m py_compile "$f" || exit 1; done'
  run harness-skills python3 - <<'PY'
import glob,re,sys,os
bad=[]
for f in glob.glob('.claude/skills/*/SKILL.md')+glob.glob('.claude/agents/*.md'):
    if os.path.islink(os.path.dirname(f)): continue  # 外部の文体マニュアルは対象外
    s=open(f,encoding='utf-8').read()
    m=re.match(r'---\n(.*?)\n---\n',s,re.S)
    if not m or 'name:' not in m.group(1) or 'description:' not in m.group(1): bad.append(f); continue
    if '/skills/' in f and not all(h in s for h in ('## 入力','## 禁止事項','## 手順','## チェックリスト')):
        bad.append(f+'（標準形式：入力／禁止事項／手順／チェックリスト）')
if bad: print('\n'.join(bad)); sys.exit(1)
PY
else
  note "SKIP harness（変更なし）"
fi
echo "----"
if [ $FAIL -eq 0 ]; then
  echo "$(date '+%F %T') $(git rev-parse --short HEAD) $(printf '%s; ' "${RESULTS[@]}")" > "$STAMP"
  echo "[check] 合格．スタンプ: $STAMP"; exit 0
else
  echo "[check] 不合格．失敗した項目を直してから再実行する．"; exit 1
fi
