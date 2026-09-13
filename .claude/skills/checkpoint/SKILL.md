---
name: checkpoint
description: 検証済みの変更がまとまった区切りで，差分確認→整合検査→ビルド→コミットを行う．「コミットして」「チェックポイント」「区切って」で使う．
argument-hint: [コミットメッセージの要旨]
allowed-tools: Read, Bash(git *), Bash(.claude/scripts/build.sh*), Bash(python3 *), Bash(npm run *)
---

チェックポイント．要旨: $ARGUMENTS

現在の差分: !`git status --short | head -40`

1. **差分を読む**．`git diff` で変更を確認し，本文と依存先・辞書の整合を検査する．定義を変えたなら依存する説明・例文・形式化・辞書が同じ変更に含まれているか．対象外の不整合があれば報告に明記する．
2. **他の作業を混ぜない**．無関係な領域の変更は別コミットにする（precommit フックが複数領域の混在を警告する）．
3. **ビルド**．`detail/` の .tex を変えたなら `.claude/scripts/build.sh` を通す（スタンプがないと commit がブロックされる）．辞書を変えたなら `npm run --silent dict -- validate`．音韻実装を変えたならそのテスト．
4. **コミット**．日本語の要旨を一行目に，本文で何を決めたか（暫定なら日付付き）を続ける．コミットは作者が依頼した場合と，検証済みの区切りに限る．push はしない．
5. **報告**．コミットハッシュ，ビルド結果（undefined 参照の数），残る未解決を短く．
