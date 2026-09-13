---
name: coinage
description: 不足語彙の造語を Fable（推論 medium）へ依頼し，候補の音形根拠と衝突確認を得る．採否と本文・辞書への統合はこのセッションが行う．「造語して」「語を作って」で使う．
argument-hint: <概念（意味・署名・用例）...>
allowed-tools: Read, Grep, Glob, Write, Bash(npm run *), Bash(python3 *), Bash(.claude/scripts/*), Agent
---

造語依頼．対象: $ARGUMENTS

今日: !`date +%F`

## 依頼前にこのセッションで行うこと
1. 既存語と派生規則を調べる（`npm run --silent dict -- search <語>` など辞書CLI，`detail/chapters/p-side/word-creation.tex`，音韻章）．
2. 略記にすぎない記号にも一律に新語を与えない．既存の長形で足りるものと，独立した語が必要なものを区別する．
3. 各概念について，必要な意味・署名（arguments の型）・用例を確定する．造語だけでは未定義の意味条件は解決しない．

## 依頼
`coiner` エージェント（Fable，推論 medium）へ，上の材料と次の要求を渡す：候補には音形の根拠と既存語との衝突確認を付けること．新しい語形は候補として出し，採否を主張しないこと．プロンプトと応答は `detail/discussion/<今日>/coinage-<主題>-fable-{prompt,response}.md` に保存する（別プロセスで呼ぶ場合は `.claude/scripts/consult.sh fable coinage-<主題> <prompt>`）．

## 依頼後
- 採否と本文への統合はこのセッションが検証する．語形の趣味判断は作者の裁定範囲なので，候補と根拠を並べて作者へ短く報告する．
- 辞書登録はパッチJSON（add／set_fields／set_upper_covers）として出し，`npm run --silent dict -- validate` の `base_hash` を付けて `apply --write` する．適用前後の辞書と検証結果を日付ログに残す．
- 分類不能・境界例は上位分類への反例として `/production coinage` の成果物に含める．
