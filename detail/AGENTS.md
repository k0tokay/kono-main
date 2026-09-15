# AGENTS.md — コノメノ詳説

人工言語コノメノの理論仕様書『コノメノ詳説 2026年版』のLaTeXソース．権威構造・更新原則・文体はルートの入口に従う：Codex は `AGENTS.override.md`，Claude は `AGENTS.md`．以下はこのディレクトリの道具の補足．

## ビルド

```bash
lualatex main-detail.tex                       # 全体コンパイル
cd chapters/p-side && lualatex phonology.tex   # 章単独コンパイル（subfiles）
```

エンジンは LuaLaTeX．`custom4-default.sty`（`~/Library/texmf/tex/latex/custom/`）が必要．
参考文献は `../bib/references.bib`．

## ファイル構成

```
main-detail.tex      ルート文書（プリアンブル + \subfile 呼び出し）
chapters/            章ごとの内容
scripts/merge_tex.py 章を1ファイルに結合（出力は ../local/build-artifacts/）
scripts/issues.py    issue 管理スクリプト
discussion/          日付ごとの議論ログ（git管理外）
```

## Issue管理

`.tex` ファイル中の `\todo{}`, `\memo{}`, `\fixme{}` マーカーに `% @issue KONO-NNNN` コメントを紐づけて追跡する．

```bash
python scripts/issues.py list              # 全issue一覧
python scripts/issues.py list --open       # openのみ
python scripts/issues.py list --file X     # ファイル絞り込み
python scripts/issues.py show KONO-0001    # 詳細表示（JSON側のタスクも表示）
python scripts/issues.py search <keyword>  # キーワード検索
python scripts/issues.py assign            # 未採番マーカーにID自動付与（dry-run）
python scripts/issues.py assign --apply    # 実際に書き込む
python scripts/issues.py sync              # .texとJSONのissue ID照合
```

IDは `.tex` 内のマーカー直前行に `% @issue KONO-NNNN` として埋め込まれる．
タスクツリー（`../archive/archive001/IssueTracker/data/kono_tasks_rec.json`）の `markers` フィールドで参照される．ステータスは `open`, `in_progress`, `blocked`, `done`, `expired`．Issue Trackerは圧力点と進行状況を探す索引に限る．
