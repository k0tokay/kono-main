#!/bin/bash
# SessionStart フック：セッション冒頭に作業座標を注入する．
# 出力は additionalContext として Claude に渡る．
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$ROOT" || exit 0
TODAY=$(date +%F)
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
LOGDIR="detail/discussion/$TODAY"
LATEST=$(ls -d detail/discussion/20*/ 2>/dev/null | sort | tail -3 | xargs -n1 basename 2>/dev/null | tr '\n' ' ')
OPEN=$(python3 detail/scripts/issues.py list --open 2>/dev/null | grep -oE 'Total: [0-9]+' | head -1)
MARKERS=$(grep -ho '\\\(todo\|memo\|fixme\|ques\|aitodo\|aimemo\){' detail/chapters/*.tex detail/chapters/*/*.tex 2>/dev/null | wc -l | tr -d ' ')
STAMP="local/build-artifacts/detail-build.ok"
if [ -f "$STAMP" ]; then BUILD="最終ビルド成功: $(cat "$STAMP")"; else BUILD="ビルドスタンプなし（/checkpoint でビルドする）"; fi
cat <<CTX
[kono-harness] $TODAY ブランチ=$BRANCH
- 今日の日付ログ: $LOGDIR （なければ .claude/scripts/newlog.sh で作る）
- 直近ログ: $LATEST
- 本文マーカー数(todo/memo/fixme/ques/ai*): $MARKERS ／ issues.py $OPEN
- $BUILD
- 権威: detail/main-detail.tex から読まれる本文だけが理論の正．ログ・archive・辞書は正ではない．
- 手順はスキルにある: /precision-review /review-respond /marker-sweep /reader-questions /counter-question /production /practice-port /coinage /codex-consult /checkpoint ．地図は .claude/README.md ．
- スキルファースト: 二度以上起こる作業は先にスキルを書く．終えたら /retro，改良は /improve-skill，新スキルは /eval-skill でドライラン．
- 未反映の Try/FAIL: $(grep -L '→ 反映' .claude/retro/*.md .claude/dryrun/*.md 2>/dev/null | grep -v README | wc -l | tr -d ' ') 件
CTX
