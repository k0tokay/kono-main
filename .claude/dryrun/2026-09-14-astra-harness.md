# Astra 最小ハーネス：読み合わせ

2026-09-14．作者の依頼「最小限のを抽出してastra用のharnessにして」による適用．対象はルート `AGENTS.override.md`．独立したスキルは作らず，既存の Claude 用入口・スキル・フックを保存した．

## 照合

| 入力・記録 | 最小版の該当箇所 | 検査結果 |
|---|---|---|
| この会話の nato の自由検討と `detail/discussion/2026-09-14/study-nato-construction-and-identity.md` | 「依頼と完了」調査，「権威と美意識」 | 本文を採択せず原典・反例・他章を調べる条件は残る．候補数・別紙数・必須retroは外せる． |
| `detail/discussion/2026-09-14/advance-endurants.md` の作者コメントと「往復1」 | 「依頼と完了」改訂，「道具と変更範囲」 | 作者が決めた改訂は本文・依存先・辞書パッチ・検証まで進められる．未決の根本方針は勝手に確定しない． |
| 誤字修正（境界ケース） | 「必要な資料だけ読む」 | 理論全体の読書や勉強工程を要求しない． |
| `detail/` からの利用 | `detail/AGENTS.md` 冒頭 | 旧ルートAGENTSを再読して固定工程を復活させる参照を，Codex／Claude別の入口へ修正した． |

これは手順の読み合わせであり，新旧ハーネスの独立実行比較ではない．理論の質の向上は未測定．

## Keep / Problem / Try

- Keep：権威・美意識・原典・反例，辞書パッチ経由の更新，既存の形式検査を維持．
- Problem：常設指示に反復作業のスキル化・固定工程・複数の記録作成が重なっていた（作者とこの会話で確認）．
- Try → 反映：その義務を最小版から外し，依頼別の完了条件と資料の条件付き参照へ差し替えた．差分は `AGENTS.override.md` の追加としてレビュー可能．Claude側へ自動反映しない．

## 機械確認

`bash .claude/scripts/formal-check.sh`：harness-settings／harness-scripts／harness-skills 合格．本文・辞書・音韻の変更なしにつき各検査はスキップ．`git diff --check` 合格．参照先の存在と CLAUDE.md のシンボリックリンク維持を確認．Codexの新規セッションでの実ロードは未実行．

根拠：[OpenAIの記事](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)，[AGENTS.override.md の優先順位](https://learn.chatgpt.com/docs/agent-configuration/agents-md)．この配置はモデル別の自動切替ではなく，当該リポジトリの Codex 用入口を切り替える．
