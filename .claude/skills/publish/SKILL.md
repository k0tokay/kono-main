---
name: publish
description: 公開版を作る．開発版（HEAD）の追跡ファイルから .tex のコメントと無効領域を落とした木を組み，ローカルの public ブランチに1コミット積む．push はしない．「公開版を作って」「publish」「公開用に」で使う．
argument-hint: [--no-verify | --dry-run]
allowed-tools: Read, Bash(git *), Bash(python3 .claude/scripts/publish.py*)
---

## 入力
- $ARGUMENTS：`--dry-run`（整形した木を作るだけ），`--no-verify`（ビルド照合を省く）．
- 現在の差分: !`git status --short | head -20`

## 禁止事項
- push しない．公開は作者が `git push origin public:main` を実行する（force push はしない）．
- 追跡ファイルに未コミットの変更があるときに走らせない（スクリプトが中止する）．先に `/checkpoint`．
- 何を除外するかを勝手に増減しない．除外処理は作者が決め，`.claude/scripts/publish.py` の `sanitize_tex` の後ろに足す．
- 開発版の作業ブランチ（main）を origin（公開）へ push しない．main の push 先は private の remote だけ．

## 手順
1. `/checkpoint` で作業ツリーを区切る．
2. `python3 .claude/scripts/publish.py --dry-run` で整形と照合（開発版と公開版を両方ビルドし，文字の出現数を比べる）を通す．失敗したら原因（無効領域の内側の `\else`，チャットのリンクの残り，整形による破損）を直す．
3. `python3 .claude/scripts/publish.py` で public ブランチにコミットする．
4. 作者に結果（コミット，整形した .tex 数，照合結果）を報告し，`git push origin public:main` を勧める．

## チェックリスト
- [ ] 照合が通った．
- [ ] チャットのリンクが公開木に残っていない（スクリプトが検査する）．
- [ ] push は作者が行う．
