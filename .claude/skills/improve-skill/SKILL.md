---
name: improve-skill
description: 振り返り（retro）とドライラン評価（dryrun）の Try/FAIL をスキル本文の差分に変換して適用する．標準形式（入力／禁止事項／手順／チェックリスト）を保ち，機械化できるものはフックへ回す．「スキルを直して」「Try を反映して」で使う．
argument-hint: <スキル名> [retro/dryrun ファイル...]
allowed-tools: Read, Grep, Glob, Edit, Write, Bash(ls *), Bash(git diff*), Bash(git log*), Bash(python3 *), Bash(.claude/scripts/quality-gate.sh*)
---

## 入力
- $0：改良するスキル名．
- $1 以降：反映元の `.claude/retro/*.md`／`.claude/dryrun/*.md`．指定がなければ，未反映（`→ 反映:` が付いていない）の Try/FAIL を持つファイルを全て集める．

未反映の候補: !`grep -L '→ 反映' "${CLAUDE_PROJECT_DIR}"/.claude/retro/*.md "${CLAUDE_PROJECT_DIR}"/.claude/dryrun/*.md 2>/dev/null | grep -v README`

## 禁止事項
- 手順を増やすだけにしない．追加した行と同じ数だけ，冗長になった行を削れないか見る．
- 禁止事項をスキル末尾に置かない．守られなかった禁止事項は，該当する手順の**直前**に再掲する（末尾では無視される）．
- 一度の改良で複数のスキルを同時に変えない．共通化が要るなら別途 `/improve-skill` を回す．
- 理論の内容や本文の記述をここで変えない．

## 手順
1. 反映元を読み，Try/FAIL を列挙する．同じ原因のものはまとめる．
2. それぞれを次のどれかに割り当てる：(a) スキル本文の変更，(b) フック・スクリプトへの機械化（`.claude/scripts/`），(c) 見送り（理由を書く）．人間の注意に頼る対策より機械判定を優先する．
3. (a) を `.claude/skills/$0/SKILL.md` に適用する．標準形式（入力／禁止事項／手順／チェックリスト）を保つ．手順の番号は振り直してよいが，他のスキルから参照される番号（精読検証パスの 1〜7 など）は保つ．
4. (b) はスクリプトを書き，`settings.json` のフックか `quality-gate.sh` に組み込む．単体テスト（stdin に JSON を流す）を通す．
5. 反映元の各 Try/FAIL に `→ 反映: <要旨>` または `→ 見送り: <理由>` を追記する．
6. `.claude/scripts/quality-gate.sh` を通す（ハーネス自身の検査を含む）．大きな変更なら `/eval-skill $0` で再評価してから本番に使う．
7. `/checkpoint` でコミットする．要旨は「<スキル名>: <何を直したか>」．

## チェックリスト
- [ ] 全ての Try/FAIL が (a)(b)(c) のどれかに割り当てられ，反映元に追記された．
- [ ] 禁止事項が該当手順の直前にある．
- [ ] 標準形式の 4 節がそろっている（quality-gate の harness-skills 検査）．
- [ ] 機械化した対策に単体テストがある．
