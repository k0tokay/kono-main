---
name: coinage
description: 不足語彙の造語を Fable（推論 medium）へ依頼し，候補の音形根拠と衝突確認を得る．採否と本文・辞書への統合はこのセッションが行う．「造語して」「語を作って」で使う．
argument-hint: <概念（意味・署名・用例）...>
allowed-tools: Read, Grep, Glob, Write, Bash(npm run *), Bash(python3 *), Bash(.claude/scripts/*), Agent
---

## 入力
- $ARGUMENTS：造語したい概念．各概念に意味・署名（arguments の型）・用例が要る．足りなければ依頼前にこのセッションで確定する．
- 既存語と派生規則の調査結果（手順1で作る）．

今日: !`date +%F`

## 禁止事項
- 略記にすぎない記号に一律に新語を与えない．既存の長形で足りるものと，独立した語が必要なものを区別する．
- 造語で意味条件の穴を埋めたことにしない．未定義の意味条件は本文側の未決として残す．
- 語形の採否をAIで決めない．趣味判断は作者の裁定範囲．
- 辞書JSONを直接編集しない．

## 手順
1. 既存語と派生規則を調べる（`npm run --silent dict -- search <語>`，`form <候補>`，`detail/chapters/p-side/word-creation.tex`，音韻章）．
2. 各概念の意味・署名・用例を確定し，新語が要るものだけを残す．
3. `coiner` エージェント（Fable，推論 medium）へ材料と要求を渡す：候補に音形の根拠と既存語との衝突確認を付けること，採否を主張しないこと．プロンプトと応答を `detail/discussion/<今日>/coinage-<主題>-fable-{prompt,response}.md` に保存する（別プロセスなら `.claude/scripts/consult.sh fable coinage-<主題> <prompt>`）．
4. 候補と根拠を並べて作者へ短く報告し，語形の裁定を受ける．
5. 採択後，辞書登録をパッチJSON（add／set_fields／set_upper_covers）として出し，`validate` の `base_hash` を付けて `apply --write`．適用前後の辞書と検証結果を日付ログに残す．
6. 分類不能・境界例は上位分類への反例として `/production coinage` の成果物に含める．

## チェックリスト
- [ ] 各概念に「新語が要る／長形で足りる」の判定と理由がある．
- [ ] 各候補に音形の根拠と衝突確認がある．
- [ ] 語形の採否を作者に委ねた記録がある．
- [ ] 辞書変更がパッチとして残り，`validate` が通る．
