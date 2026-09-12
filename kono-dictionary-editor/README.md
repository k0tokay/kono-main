# コノメノ用の辞書編集ソフト

人工言語コノメノの辞書を編集するためのWebアプリケーション。

## 保存方法

- `ブラウザに保存`（Ctrl/⌘+S）は編集中の辞書をそのブラウザの `localStorage` に保存する。
- `npm run dev` では、`辞書本体を上書き`（Ctrl/⌘+Shift+S）が `src/data/konomeno-v5.json` を直接更新する。ファイルの選択や再アップロードは不要。
- デプロイ版の `ファイルを上書き`（Ctrl/⌘+Shift+S）は、読み込み時に選択したローカルJSONへ保存する。組み込み辞書から編集を始めた場合は、初回保存時に書き込み先を選択する。
- ファイルの直接上書きには File System Access API を利用するため、Chrome / Edgeなどの対応ブラウザが必要。未対応ブラウザでは `ダウンロード` を利用する。

開発サーバー専用の書き込みAPIは本番ビルドに含まれない。GitHub Pagesでは、上書き対象は利用者が明示的に選択したローカルファイルであり、デプロイ済みの辞書やGitHubリポジトリは変更されない。正典を更新するには、ローカルで辞書本体を更新してコミット・再デプロイする。

## LLM用CLI

`src/data/konomeno-v5.json` 全体をコンテキストへ載せず、必要な語とオントロジー近傍だけをJSONで取得できる。

```bash
npm run --silent dict -- stats --pretty
npm run --silent dict -- search --translation 建物 --limit 10
npm run --silent dict -- show id:77 --pretty
npm run --silent dict -- context id:77 --depth 2 --limit 30
npm run --silent dict -- form mosto --limit 10
npm run --silent dict -- validate --pretty
npm run --silent dict -- schema --pretty
```

同じ綴りが複数カテゴリに存在しうるため、更新時は必ず数値IDを使う。`entry:ka` のような参照が複数語に一致した場合、CLIは一つを勝手に選ばずエラーにする。

### 変更パッチ

CLIからの変更は、辞書JSONの直接置換ではなく、次の四操作を持つパッチで行う。

- `add`
- `set_fields`
- `set_upper_covers`
- `delete`

`lower_covers` は直接編集できない。構造操作は対象となる `upper_covers` と `lower_covers` を同時に更新する。既存の非対称リンクは「リンク欠落」か「削除の痕跡」かを判別できないため、CLIは辞書全体を一方から自動再構築しない。

```json
{
  "version": 1,
  "base_hash": "statsやvalidateが返したhash",
  "operations": [
    {
      "op": "set_upper_covers",
      "id": 123,
      "from": [45],
      "to": [67, 89]
    },
    {
      "op": "set_fields",
      "id": 123,
      "expect": { "entry": "oldword" },
      "set": { "entry": "newword", "translations": ["新しい訳"] }
    },
    {
      "op": "delete",
      "id": 456,
      "expect": { "entry": "obsolete-word" },
      "reconnect": "parents",
      "reference_policy": "reject"
    }
  ]
}
```

`delete.reconnect` は、削除語の子を元の親へ付け替える `parents` と、付け替えない `none` のどちらかを必ず指定する。`reference_policy` は `arguments` / `relations` から参照されていた場合に停止する `reject` と、それらの参照も削除する `remove` のどちらかを必ず指定する。

まずプレビューする。

```bash
npm run --silent dict -- apply proposal.json --pretty
```

実際に正典へ保存するときだけ `--write` を付ける。書き込み時は `base_hash` が必須で、調査後に辞書が変更されていれば保存を拒否する。

```bash
npm run --silent dict -- apply proposal.json --write --pretty
```
