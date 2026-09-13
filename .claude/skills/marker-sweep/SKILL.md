---
name: marker-sweep
description: 本文に残る memo/todo/ques/fixme マーカーを章ごとに棚卸しして裁く（memo/todo掃討）．「マーカーを掃討」「todoを片付けて」で使う．
argument-hint: <章ファイル> [--dry-run]
allowed-tools: Read, Grep, Glob, Edit, Write, Bash(python3 *), Bash(npm run *), Bash(git *), Bash(.claude/scripts/*), Agent
---

memo/todo 掃討．対象: $ARGUMENTS

今日: !`date +%F` ／ 対象のマーカー: !`grep -nE '\\(todo|memo|fixme|ques)\{' "${CLAUDE_PROJECT_DIR}/$0" 2>/dev/null | head -60; true`

## 手順
1. **棚卸し**．マーカーを列挙し，(i) 誤植・既解決（本文の別箇所や直近の改稿で答えが出ている），(ii) 単純決定（辞書・実装・定義で検証すれば決まる），(iii) 要議論，に分ける．検証には辞書CLI（`npm run --silent dict -- ...`），音韻実装（`kono-phonology/konophon`），本文の定義を実際に当てる．検算は `verifier` へ委ねてよい．
2. **処置**．(i) は削除または散文化．(ii) は本文に暫定表示（日付付き）で書く．(iii) は設計上の問いにまとめ `/codex-consult` へ一往復投げ，結論を暫定採択して本文へ入れる．文献調査・執筆作業・作者主体（P側，趣味判断）の項目はマーカーを残し，「何が決まれば閉じるか」まで書き直す．
3. **マーカーを消すだけにしない**．マーカーを一文に置き換えて終わらせず，それを含む表・節・remark の存在意義を検討する．他章と重複する表は削る．参照三行だけになった節は前節へ畳む．todo だけの節は消して移植先に todo を置く．
4. **隣接する記述の失効を点検する**．採択によって「未決である」「書き直すかは未決」といった隣の文が嘘になる．置換した箇所の前後と，同じ主題を扱う他章の文を必ず読み直す．
5. **記録**．`detail/discussion/<今日>/marker-sweep-<章名>.md` に処置一覧を表で残す（行，元マーカー，分類，処置，根拠）．codex のプロンプトと回答は `consult.sh` が同じ日付ディレクトリへ保存する．
6. **検証**．`/checkpoint` で全体ビルドを通してからコミットする．辞書側の作業は本文に「辞書が移行対象」と書き，パッチとして別に出す．

`--dry-run` が付いていれば手順1と処置案の表だけを作り，本文を変更しない．
