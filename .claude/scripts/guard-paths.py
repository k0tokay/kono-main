#!/usr/bin/env python3
"""PreToolUse フック（Edit|Write|MultiEdit|NotebookEdit|Bash）．
書き込んではいけない場所への編集を拒否する（exit 2 → ブロック，stderr が Claude に返る）．

- archive/       : 過去資料．読むだけ．
- konomeno-v5.json: 辞書データは手で編集せず，npm run dict のパッチ機構で変更する．
- git commit     : precommit-check.py に委譲．
"""
import json, os, re, subprocess, sys

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DICT = "kono-dictionary-editor/src/data/konomeno-v5.json"

def deny(msg):
    sys.stderr.write(msg + "\n")
    sys.exit(2)

def rel(p):
    p = os.path.abspath(os.path.join(ROOT, p)) if not os.path.isabs(p) else p
    try:
        return os.path.relpath(p, ROOT)
    except ValueError:
        return p

def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    tool = data.get("tool_name", "")
    ti = data.get("tool_input", {}) or {}
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        path = rel(ti.get("file_path") or ti.get("notebook_path") or "")
        if path.startswith("archive/"):
            deny(f"[guard] {path} は archive/ 配下．過去資料は読むだけで編集しない（AGENTS.md 権威構造）．")
        if path == DICT:
            deny(f"[guard] 辞書データは直接編集しない．パッチJSONを書き `npm run --silent dict -- apply <patch> --write` で適用する（base_hash を validate で取る）．")
        return
    if tool == "Bash":
        cmd = ti.get("command", "") or ""
        if re.search(r"(^|[;&|(]\s*)git\s+commit\b", cmd, re.M):
            if re.search(r"(^|[;&|(]\s*)git\s+add\b", cmd, re.M):
                deny("[guard] git add と git commit を同じコマンドに書かない．検査はコマンド実行前のステージ状態を見るので，先に git add を別コマンドで実行してから git commit する．")
            r = subprocess.run([sys.executable, os.path.join(ROOT, ".claude/scripts/precommit-check.py")],
                               capture_output=True, text=True)
            if r.returncode != 0:
                deny(r.stderr or r.stdout or "[guard] precommit-check に失敗")
            if r.stdout.strip():
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                          "permissionDecision": "allow",
                                                          "additionalContext": r.stdout.strip()}}, ensure_ascii=False))
            return
        if re.search(r"(>|>>|sed\s+-i|tee)\s*\S*archive/", cmd):
            deny("[guard] archive/ 配下への書き込みは行わない．")
        if re.search(r"(>|>>|sed\s+-i|tee)\s*\S*konomeno-v5\.json", cmd):
            deny("[guard] 辞書データはパッチ機構（npm run dict -- apply）で変更する．")

if __name__ == "__main__":
    main()
