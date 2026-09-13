#!/bin/bash
# 外部モデルへの一往復．プロンプトと応答を日付ログに残す．
#   .claude/scripts/consult.sh <codex|fable|opus|sonnet> <名前> <プロンプトファイル> [追加フラグ...]
# 生成物（detail/discussion/YYYY-MM-DD/）:
#   <名前>-<相手>-prompt.md      プロンプトの写し
#   <名前>-<相手>-response.md    応答本文
#   <名前>-<相手>-response.json  生の応答（claude -p のみ）
# どの相手も read-only で呼ぶ．採否と本文への統合は主担当（このセッション）が行う．
set -u
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
WHO="$1"; NAME="$2"; PROMPT="$3"; shift 3
LOG="$ROOT/detail/discussion/$(date +%F)"; mkdir -p "$LOG"
BASE="$LOG/$NAME-$WHO"
cp "$PROMPT" "$BASE-prompt.md"
CODEX_MODEL="${KONO_CODEX_MODEL:-gpt-5.6-sol}"
CODEX_EFFORT="${KONO_CODEX_EFFORT:-high}"
case "$WHO" in
  codex)
    ( cd "$ROOT" && codex exec -s read-only -m "$CODEX_MODEL" -c "model_reasoning_effort=\"$CODEX_EFFORT\"" \
        --ephemeral -o "$BASE-response.md" "$@" - < "$PROMPT" ) > "$BASE-events.log" 2>&1
    RC=$?
    ;;
  fable|opus|sonnet)
    EFFORT="${KONO_CLAUDE_EFFORT:-medium}"
    [ "$WHO" = "fable" ] && EFFORT="${KONO_FABLE_EFFORT:-medium}"
    ( cd "$ROOT" && claude -p --model "$WHO" --effort "$EFFORT" --output-format json \
        --permission-mode default \
        --allowedTools "Read,Grep,Glob,Bash(git diff:*),Bash(git log:*),Bash(git show:*),Bash(python3 detail/scripts/*),Bash(npm run --silent dict -- validate*),Bash(npm run --silent dict -- show*)" \
        --disallowedTools "Edit,Write,MultiEdit,NotebookEdit" "$@" < "$PROMPT" ) > "$BASE-response.json"
    RC=$?
    python3 - "$BASE-response.json" "$BASE-response.md" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    open(sys.argv[2], "w").write(d.get("result", "") or "")
    u = d.get("usage", {})
    print(f"cost={d.get('total_cost_usd')} out={u.get('output_tokens')} stop={d.get('stop_reason')}")
except Exception as e:
    print("response.json の解析に失敗:", e)
PY
    ;;
  *) echo "相手は codex|fable|opus|sonnet"; exit 1;;
esac
echo "rc=$RC prompt=$BASE-prompt.md response=$BASE-response.md"
exit $RC
