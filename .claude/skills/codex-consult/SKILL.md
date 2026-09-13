---
name: codex-consult
description: S側の要議論項目を codex（gpt-5.6-sol, reasoning high, read-only）へ一往復投げて反論を得る．プロンプトと応答は日付ログに保存され，採否はこのセッションが決める．「codexに聞いて」「反論をもらって」で使う．
argument-hint: <主題名> <問い（または問いを書いたファイル）>
allowed-tools: Read, Grep, Glob, Write, Bash(.claude/scripts/consult.sh *), Bash(codex *)
---

codex 一往復．引数: $ARGUMENTS

## プロンプトの組み立て
`detail/discussion/<今日>/<主題>-codex-prompt.md` を書く．含めるもの：
- 役割：あなたは反例係．読み取りのみ．本文・辞書・gitを変更しない．回答は日本語，根拠のファイルと行を付ける．
- 最初に `AGENTS.md` と対象章・依存箇所を読むこと．唯一の権威は `detail/main-detail.tex` から読まれる本文．過去ログを根拠に採択を変更しないこと．
- 問い：設計上の問いとして定式化する（何を決めれば閉じるか）．現行案と代替案，最小例，制約（新しい形式的装置の禁止，時刻指標の新設禁止など該当するもの）．
- 成果物の形：支持／修正／撤回と理由，最強の反論，批判が致命的／修正可能／好みのどれか，決定を覆しうる観察，残る未決点．同意するためのレビューではなく診断と処方を両方攻撃すること．

## 実行
```
.claude/scripts/consult.sh codex <主題> detail/discussion/<今日>/<主題>-codex-prompt.md
```
応答は `<主題>-codex-response.md`．

## 採否
- 一往復（必要なら二往復）で暫定採択し，本文へ日付付き「暫定」で入れる．作者には結果と反対理由だけを短く報告する．
- AI同士の合意は根拠にしない．原典・形式的帰結・具体例・変更の波及で検証する．
- 根の変更（設計規範・骨格木・体系の型）と趣味判断（語形・命名・文体）は採択せず，作者の裁定に回す．
