# コノメノ・ハーネス

`workflow/workflow.tex` に散文で書いていた開発ワークフローを，Claude Code のハーネス（スキル・サブエージェント・フック）へ移したもの．**手順の正はここ**，理論の正は『詳説』本文，美意識と心構えは `workflow/workflow.tex` に残す．

構成は三つのピースからなる（スキルファースト駆動開発の型）．
1. **業務スキル**：個別タスクの手順．標準形式「入力／禁止事項／手順／チェックリスト」にそろえる．守られにくい禁止事項は該当手順の直前に再掲する．
2. **品質ガード**：`scripts/quality-gate.sh`．人間レビューの前に機械判定で合否を返す．コミットはこれを通らないとフックが拒否する．
3. **自己進化スキル**：`/retro`（Keep/Problem/Try）→ `/improve-skill`（スキル差分に変換，機械化できるものはフックへ）→ `/eval-skill`（過去タスクでドライラン，再現性・改善度・副作用）．記録は `retro/` と `dryrun/` に残す．

二度以上起こる作業は，依頼を実行する前にスキルを書く．依頼の定型：「〜のスキルを作って．要件は質問して詰めて．スキル自体は再現性をドライランで評価して．」

## 地図（workflow.tex の節 → 部品）

| 旧節 | 部品 | 種類 |
|---|---|---|
| 文体について | `skills/write-concise-japanese`（→ `workflow/style-manual/…_v5` へのシンボリックリンク）＋ `scripts/tex-lint.py` | スキル＋PostToolUse フック |
| 権威ある本文 | `scripts/session-context.sh`，`scripts/guard-paths.py` | SessionStart／PreToolUse フック |
| 読者質問パス | `/reader-questions` | スキル |
| 反問プロンプト | `/counter-question` | スキル |
| 精読検証パス 1〜4 | `/precision-review`（別文脈なら `precision-reviewer` エージェント） | スキル／エージェント |
| 精読検証パス 5〜7 | `/review-respond` | スキル |
| AIの分担と作業の区切り | `investigator`，`verifier`，`coiner` エージェント；`/checkpoint`＋`scripts/quality-gate.sh`＋`scripts/precommit-check.py` | エージェント／スキル／フック |
| 制作→ワークフロー（手順の改良） | `/retro`，`/improve-skill`，`/eval-skill`；`retro/`，`dryrun/` | スキル／記録 |
| フィードバック経路付きの制作 | `/production` | スキル |
| memo／todo掃討 | `/marker-sweep` | スキル |
| 実践編の制作・移植 | `/practice-port` | スキル |
| 造語依頼（Fable, medium） | `/coinage` → `coiner` | スキル／エージェント |
| codex 一往復 | `/codex-consult` → `scripts/consult.sh` | スキル／スクリプト |

## スキル（`/名前` で起動）

- `/precision-review <章>`：精読レビューを日付ログに作る．本文は変えない．
- `/review-respond <対象名>`：作者コメントに応答し，本文と依存先を直し，レビュー状態を更新する．
- `/marker-sweep <章> [--dry-run]`：memo/todo/ques/fixme を棚卸しして裁く．
- `/reader-questions <範囲> [--edit]`：読者の疑問をログする．`--edit` で編集まで．
- `/counter-question [議題]`：反問モードで議論する．
- `/production <経路> <対象>`：フィードバック経路に位置づけて制作する．
- `/practice-port <旧稿範囲> <移植先>`：旧稿から実践編へ移植する．
- `/coinage <概念…>`：造語を Fable に依頼する．
- `/codex-consult <主題> <問い>`：codex へ一往復投げる．
- `/checkpoint [要旨]`：差分確認→品質ガード→コミット．
- `/retro <スキル> <主題>`：Keep/Problem/Try を `retro/` に残す．
- `/improve-skill <スキル>`：未反映の Try/FAIL をスキル差分にして適用する．
- `/eval-skill <スキル|--all>`：過去タスクでドライラン評価し `dryrun/` に残す．

## サブエージェント（`agents/`）

| 名前 | モデル | 役 |
|---|---|---|
| `investigator` | sonnet | 論点調査（読み取り専用，出典付き） |
| `verifier` | sonnet | 検算・ビルド・辞書照合（本文は変えない） |
| `coiner` | fable / medium | 造語候補（採否は主張しない） |
| `precision-reviewer` | opus / high | 精読レビュー作成を別文脈で |

主担当（このセッション）が起動と統合を行い，権威構造と確認の窓口を一本化する．AI同士の合意は根拠にしない．

## フック（`settings.json`）

| イベント | スクリプト | 何をするか |
|---|---|---|
| SessionStart | `scripts/session-context.sh` | 日付ログの場所，直近ログ，マーカー数，ビルド状態，権威の一行を注入 |
| PreToolUse (Edit/Write/Bash) | `scripts/guard-paths.py` | `archive/` と辞書JSONへの直接書き込みを拒否．`git commit` の前に `precommit-check.py` を走らせる |
| PostToolUse (Edit/Write) | `scripts/tex-lint.py` | `detail/` の .tex に対し，araidashi・環境の対応・ラベルと表の増加・日付なし「暫定」・残った aitodo/aimemo を報告 |

`precommit-check.py` は，品質ガードのスタンプ（`local/build-artifacts/quality-gate.ok`，`scripts/quality-gate.sh` が書く）がステージ済みファイルより新しいことを要求し，複数領域の混在と gitignore 対象の混入を警告する．検査はコマンド実行前のステージ状態を見るので，`git add` と `git commit` は別のコマンドに分ける（同じ行に書くと未ステージのまま検査される）．

## スクリプト（`scripts/`）

- `quality-gate.sh [--full]`：変更領域に応じて，本文ビルド＋文体lint＋issues同期＋スクリプトのテスト，辞書 validate＋テスト，音韻テスト，ハーネス自身（settings.json，スクリプト構文，スキルの標準形式）を検査し，合格でスタンプを書く．
- `build.sh [--full] [章.tex]`：全体ビルド（＋章単独）．`--full` は bibtex 込み．
- `consult.sh <codex|fable|opus|sonnet> <名前> <prompt.md>`：外部モデルへ read-only で一往復．プロンプトと応答を今日の日付ログへ保存．環境変数 `KONO_CODEX_MODEL`（既定 gpt-5.6-sol），`KONO_CODEX_EFFORT`（high），`KONO_FABLE_EFFORT`（medium）．
- `newlog.sh`：今日の日付ログディレクトリを作る．

## 注意

- `workflow/` は gitignore 対象（整理がつき次第公開）．`skills/write-concise-japanese` のリンク先はそこにあるので，クローン先では切れる．
- 辞書CLIは `kono-dictionary-editor/` で `npm run --silent dict -- <search|show|context|form|stats|validate|schema|apply>` として実行する．
- 手順の改良（制作→ワークフローの経路）は，このディレクトリのスキル・フックへ差分として返す．
