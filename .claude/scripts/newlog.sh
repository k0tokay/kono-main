#!/bin/bash
# 今日の日付ログディレクトリを作り，パスを出力する．
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
D="$ROOT/detail/discussion/$(date +%F)"
mkdir -p "$D" && echo "$D"
