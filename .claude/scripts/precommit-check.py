#!/usr/bin/env python3
"""git commit の直前検査（guard-paths.py から呼ばれる．単体でも実行可）．

検査：
1. ステージに detail の .tex があれば，ビルドスタンプ（local/build-artifacts/detail-build.ok）が
   ステージ済み .tex より新しく，かつ成功していること．なければ拒否．
2. 無関係な領域（detail / 辞書 / 音韻 / harness / その他）が一つのコミットに混ざっていれば警告（拒否はしない）．
3. detail/discussion/ や local/ は gitignore 済みだが，force add されていれば警告．
終了コード 0 = 許可（stdout は追加コンテキスト），2 = 拒否（stderr が理由）．
"""
import os, subprocess, sys

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STAMP = os.path.join(ROOT, "local/build-artifacts/detail-build.ok")

def staged():
    r = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if l.strip()]

def area(p):
    if p.startswith("detail/"): return "detail"
    if p.startswith("kono-dictionary-editor/"): return "dictionary"
    if p.startswith("kono-phonology/"): return "phonology"
    if p.startswith(".claude/") or p in ("AGENTS.md", "CLAUDE.md"): return "harness"
    if p.startswith(("sketch/", "introduction/", "story/")): return "books"
    return "other"

def main():
    files = staged()
    notes = []
    if not files:
        print("[precommit] ステージされた変更なし．")
        return 0
    tex = [f for f in files if f.startswith("detail/") and f.endswith(".tex")]
    if tex:
        if not os.path.exists(STAMP):
            sys.stderr.write("[precommit] detail の .tex がステージされているがビルドスタンプがない．"
                             "先に `.claude/scripts/build.sh` を通す（/checkpoint）．\n")
            return 2
        st = os.path.getmtime(STAMP)
        newer = [f for f in tex if os.path.exists(os.path.join(ROOT, f)) and os.path.getmtime(os.path.join(ROOT, f)) > st]
        if newer:
            sys.stderr.write("[precommit] ビルドスタンプより新しい .tex がある: " + ", ".join(newer) +
                             " ．`.claude/scripts/build.sh` を再実行してからコミットする．\n")
            return 2
        with open(STAMP) as fh:
            notes.append("[precommit] ビルド確認済み: " + fh.read().strip())
    areas = sorted({area(f) for f in files})
    if len(areas) > 1:
        notes.append("[precommit] 警告: 複数領域が同じコミットに混在 " + str(areas) +
                     " ．無関係な変更を混ぜないこと（workflow: AIの分担と作業の区切り）．意図的なら続行してよい．")
    leaked = [f for f in files if f.startswith(("detail/discussion/", "local/", "archive/", "workflow/"))]
    if leaked:
        notes.append("[precommit] 警告: gitignore 対象がステージされている: " + ", ".join(leaked))
    print("\n".join(notes))
    return 0

if __name__ == "__main__":
    sys.exit(main())
