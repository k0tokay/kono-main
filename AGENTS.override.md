# コノメノ — Codex / Astra

人工言語の理論そのものを創作するプロジェクト．Codex の作業方針はこのファイルに集約する．`AGENTS.md`・`CLAUDE.md`・`.claude/skills/` の工程は Claude 用であり，明示的に依頼されたときだけ使う．モデル設定は変更しない．

## 権威と美意識

- 理論の唯一の権威は `detail/main-detail.tex` から読み込まれる有効本文．ログ・旧稿にしかない決定は未採用．辞書 `kono-dictionary-editor/src/data/konomeno-v5.json` は実装データの正であり，理論の採択を意味しない．
- 少ない原理で多くを説明し，各部が互いを必要とする統一感を重視する．普遍性・分類・突飛さが作者の好み．整った分類表や文章量だけを成果としない．詳しい美意識は `workflow/workflow.tex` の該当節にある．
- 辞書や具体例が分類に収まらなければ，例外処理で済ませず理論への反例として扱う．AI同士の合意を根拠にしない．新装置の案は，二項関係・引き下げ・フレーム・談話モジュール・語彙仕様で担えない仕事を示す．

## 依頼と完了

- 調査・勉強・レビューでは採択や本文変更をしない．使える既存理論を原典で調べ，具体例と他章に照らし，推す案・理由・変わる既存裁定・未解決点を返す．根の問いでは設計規範も検討対象にする．未読の原典や未検証の範囲を明記する．
- 制作・改訂を依頼されたら，必要な検討から本文の差分，依存する説明・例文・形式化・辞書の更新，変更に応じた検証まで進める．提案や最初の実装だけで止めない．根本方針が未決で作者の選択を要する部分は，判断材料を揃えて返す．
- 手順・分担・出力形式は課題に合わせる．毎回のスキル作成，retro，固定数の候補や報告書は不要．繰り返す失敗があれば，効く箇所だけ手順を直す提案をする．
- 本文には現行の定義・規則と理解に必要な説明を置く．検討中の主張は近くに明記し，改訂経緯・棄却案は `detail/discussion/YYYY-MM-DD/` に残す．説明は簡潔な日本語とし，定義と帰結，事実と提案を分ける．

## 必要な資料だけ読む

対象と依存箇所を選んで読む．誤字修正や実装だけの変更で理論全体を通読しない．理論の判断に関わる場合の入口は以下．パスはリポジトリルート基準．

- オントロジー：`detail/chapters/s-side/upper-classification.tex`「構築方法論」．分類・規範を検討するときは設計規範・分類作法・検証方法・記述規則を照合する．
- 意味論・冠詞・談話：`detail/chapters/s-side/formal-semantics.tex`「引き下げ対応と超内包性」．文法：同ディレクトリの `formal-grammar.tex` 冒頭定義．
- 音韻・造語・文字：`detail/chapters/p-side/phonology.tex` と `kono-phonology/konophon`．
- 文の組み立て・実践：`sketch/main-sketch.tex`（作者未レビュー）と `detail/chapters/practice/practice-foundations.tex`．素描と詳説が衝突すれば詳説を優先．旧稿は由来を調べるときだけ参照する．
- 文献：`bib/references.bib` と `bib/` の原典．`archive/` と旧Issue Trackerは過去案・未解決点を探す資料であり，現行仕様や達成の証拠にしない．
- 長い文章の執筆・推敲：`workflow/style-manual/` の最新版の文体規範．`workflow/workflow.tex` は美意識・文体の参照先とし，そこから Claude の固定工程を読み込まない．

## 道具と変更範囲

- 辞書は `kono-dictionary-editor/` で `npm run --silent dict -- <command>`．`search`・`show`・`context` で調査，`schema`・`validate` で確認し，変更は `apply <patch> --write` を使う．JSON を直接編集しない．`archive/` は読み取り専用．
- 本文は LuaLaTeX．既存の検証はルートで `bash .claude/scripts/formal-check.sh`（変更領域を選んで実行）．コミット前に通す．Issue の調査には `python3 detail/scripts/issues.py`．
- `.claude/scripts/` は共用できる道具．Claude のフックが Codex でも自動実行されるとは仮定しない．ローカルの調査・編集・検証は依頼の範囲で進め，コミット・push・公開は依頼された場合に行う．辞書エディタは main への push で公開される．
