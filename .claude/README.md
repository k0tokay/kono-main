# コノメノ・ハーネス

このディレクトリの工程は Claude 用．Codex / Astra の最小ハーネスはルートの `AGENTS.override.md` にあり，Codex は同階層の `AGENTS.md` よりそちらを優先して読む．スクリプトは共用するが，フックの自動実行は共用されない．モデルの自動選択は行わない．

`workflow/workflow.tex` に散文で書いていた開発ワークフローを，Claude Code のハーネス（スキル・サブエージェント・フック）へ移したもの．**手順の正はここ**，理論の正は『詳説』本文，美意識と心構えは `workflow/workflow.tex` に残す．

構成は次の三つ．
1. **業務スキル**：個別タスクの手順．標準形式「入力／禁止事項／手順／チェックリスト」．守られにくい禁止事項は該当手順の直前に再掲する．各スキルは `AGENTS.md` の**アンカー**（作業種別ごとに最初に読む一つ）を入力に持つ．
2. **形式検査**：`scripts/formal-check.sh`．機械で判定できるもの（ビルド・文体lint・辞書validate・テスト・ハーネス構文）だけを検査し，コミット前に通す．理論の質は判定しない．人間のレビューを代替しない．
3. **ループを閉じる部品**：旧ワークフローの「フィードバック経路付きの制作」と同じ一つのループで，戻し先だけが違う．本文へ戻す（`/production practice|coinage`），構築方法論へ戻す（`/production methodology`），手順へ戻す（`/retro` → `/improve-skill`）．`/eval-skill` は新スキルを過去の記録と読み合わせる補助で，実行評価は高価なので常設にしない．

二度以上起こる作業は，依頼を実行する前にスキルを書く（スキルファースト）．手順の差分は作者が見る．

## 地図（workflow.tex の節 → 部品）

| 旧節 | 部品 | 種類 |
|---|---|---|
| 文体について | `skills/write-concise-japanese`（→ `workflow/style-manual/…_v5` へのシンボリックリンク）＋ `scripts/tex-lint.py` | スキル＋PostToolUse フック |
| 権威ある本文 | `scripts/session-context.sh`，`scripts/guard-paths.py` | SessionStart／PreToolUse フック |
| 読者質問パス | `/reader-questions`；上流の通読所感は `/read-through` | スキル |
| 反問プロンプト | `/counter-question` | スキル |
| 通読所感（上流） | `/read-through`（別文脈では `reader`） | スキル／エージェント |
| 精読検証パス 1〜4 | `/precision-review`（別文脈なら `precision-reviewer` エージェント） | スキル／エージェント |
| 精読検証パス 5〜7 | `/review-respond` | スキル |
| AIの分担と作業の区切り | `investigator`，`verifier` エージェント；`/checkpoint`＋`scripts/formal-check.sh`＋`scripts/precommit-check.py` | エージェント／スキル／フック |
| 制作→ワークフロー（手順の改良） | `/retro` → `/improve-skill`（`/eval-skill` は補助）；`retro/`，`dryrun/` | スキル／記録 |
| フィードバック経路付きの制作 | `/production` | スキル |
| memo／todo掃討 | `/marker-sweep` | スキル |
| 辞書の配置の状態 | `/placement-triage` | スキル |
| 実践編の制作・移植 | `/practice-port` | スキル |
| 造語 | `/coinage`（主担当が直接．検査は `kono-phonology/scripts/check_candidates.py`） | スキル |
| codex 一往復 | `/codex-consult` → `scripts/consult.sh` | スキル／スクリプト |

## スキル（`/名前` で起動）

- `/study <主題>`：根の問いの勉強工程．文献→読書ノート→候補基準→他章への横断照合→構築方法論への規範レコード提案．分類の編集はこの後．
- `/read-through <章|all>`：本文だけを読者として通読し，疑問と違和感を散文で書く（番号・状態なし）．精読より上流．
- `/precision-review <章>`：精読レビューを日付ログに作る．本文は変えない．
- `/review-respond <対象名>`：作者コメントに応答し，本文と依存先を直し，レビュー状態を更新する．
- `/marker-sweep <章> [--dry-run]`：memo/todo/ques/fixme を棚卸しして裁く．
- `/placement-triage <対象>`：辞書の語に配置の状態（配置／暫定配置／未配置）を付ける．
- `/reader-questions <範囲> [--edit]`：読者の疑問をログする．`--edit` で編集まで．
- `/counter-question [議題]`：反問モードで議論する．
- `/production <経路> <対象>`：フィードバック経路（practice／coinage／methodology）に位置づけて制作する．
- `/practice-port <旧稿範囲> <移植先>`：旧稿から実践編へ移植する．
- `/coinage <概念…>`：造語を Fable に依頼する．
- `/codex-consult <主題> <問い>`：codex へ一往復投げる．
- `/checkpoint [要旨]`：差分確認→形式検査→コミット．
- `/retro <スキル> <主題>`：Keep/Problem/Try を `retro/` に残す．
- `/improve-skill <スキル>`：未反映の Try/FAIL をスキル差分にして適用する．
- `/eval-skill <スキル|--all> [--run]`：過去の記録と読み合わせて手順の抜け・過剰を出す．`--run` で実行評価．

## サブエージェント（`agents/`）

| 名前 | モデル | 役 |
|---|---|---|
| `reader` | opus / high | 通読所感を別文脈で（ログを見ない読者） |
| `investigator` | sonnet | 論点調査（読み取り専用，出典付き．借用概念は原典に当たる） |
| `verifier` | sonnet | 検算・ビルド・辞書照合（本文は変えない） |
| `precision-reviewer` | opus / high | 精読レビュー作成を別文脈で |

主担当（このセッション）が起動と統合を行い，権威構造と確認の窓口を一本化する．AI同士の合意は根拠にしない．

## フック（`settings.json`）

| イベント | スクリプト | 何をするか |
|---|---|---|
| SessionStart | `scripts/session-context.sh` | 日付ログの場所，直近ログ，マーカー数，ビルド状態，権威の一行を注入 |
| PreToolUse (Edit/Write/Bash) | `scripts/guard-paths.py` | `archive/` と辞書JSONへの直接書き込みを拒否．`git commit` の前に `precommit-check.py` を走らせる |
| PostToolUse (Edit/Write) | `scripts/tex-lint.py` | `detail/` の .tex に対し，araidashi・環境の対応・ラベルと表の増加・日付なし「暫定」・残った aitodo/aimemo を報告 |

`precommit-check.py` は，形式検査のスタンプ（`local/build-artifacts/formal-check.ok`，`scripts/formal-check.sh` が書く）がステージ済みファイルより新しいことを要求し，複数領域の混在と gitignore 対象の混入を警告する．検査はコマンド実行前のステージ状態を見るので，`git add` と `git commit` は別のコマンドに分ける（同じ行に書くと未ステージのまま検査される）．

## スクリプト（`scripts/`）

- `formal-check.sh [--full]`：変更領域に応じて，本文ビルド＋文体lint＋issues同期＋スクリプトのテスト，辞書 validate＋テスト，音韻テスト，ハーネス自身（settings.json，スクリプト構文，スキルの標準形式）を検査し，合格でスタンプを書く．
- `build.sh [--full] [章.tex]`：全体ビルド（＋章単独）．`--full` は bibtex 込み．
- `consult.sh <codex|fable|opus|sonnet> <名前> <prompt.md>`：外部モデルへ read-only で一往復．プロンプトと応答を今日の日付ログへ保存．環境変数 `KONO_CODEX_MODEL`（既定 gpt-5.6-sol），`KONO_CODEX_EFFORT`（high），`KONO_FABLE_EFFORT`（medium）．
- `def-inventory.py <file.tex>`：章の定義単位（節点・\rele・環境数）を列挙し定義票の雛形を出す．
- `active-lines.py <file.tex> [--inactive]`：`\iffalse`／`\if0` を除いた有効行範囲を出す．精読レビューの冒頭に使う．
- `newlog.sh`：今日の日付ログディレクトリを作る．

## 注意

- `workflow/` は gitignore 対象（整理がつき次第公開）．`skills/write-concise-japanese` のリンク先はそこにあるので，クローン先では切れる．
- 辞書CLIは `kono-dictionary-editor/` で `npm run --silent dict -- <search|show|context|form|stats|validate|schema|apply>` として実行する．
- 手順の改良（制作→ワークフローの経路）は，このディレクトリのスキル・フックへ差分として返す．
