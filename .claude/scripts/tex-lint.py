#!/usr/bin/env python3
"""PostToolUse フック（Edit|Write）．detail/chapters 配下の .tex を編集した直後に文体・構造の機械検査を行う．
拒否はしない．結果を additionalContext として返す（問題がなければ何も出さない）．

検査項目（workflow「文体について」「memo/todo掃討」から機械化できるもの）：
- araidashi 環境の使用（禁止）
- \\begin/\\end の環境名の対応
- git HEAD と比べた \\label と tabular の増加（ラベルを増やさない方針，表は少なくする方針）
- 「暫定」を含む行に日付（YYYY-MM-DD）がない
- aitodo/aimemo が残っている（AIへの指示．処理後に消すか todo/memo へ戻す）
"""
import json, os, re, subprocess, sys

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def head_text(rel):
    r = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""

def strip_comments(s):
    return "\n".join(re.sub(r"(?<!\\)%.*", "", l) for l in s.splitlines())

def env_balance(s):
    stack, problems = [], []
    for m in re.finditer(r"\\(begin|end)\{([^}]*)\}", s):
        kind, name = m.group(1), m.group(2)
        line = s.count("\n", 0, m.start()) + 1
        if kind == "begin":
            stack.append((name, line))
        else:
            if stack and stack[-1][0] == name:
                stack.pop()
            else:
                problems.append(f"L{line}: \\end{{{name}}} が対応しない（直前の begin: {stack[-1][0] if stack else 'なし'}）")
    problems += [f"L{l}: \\begin{{{n}}} が閉じていない" for n, l in stack]
    return problems[:5]

def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    path = (data.get("tool_input") or {}).get("file_path") or ""
    rel = os.path.relpath(os.path.abspath(path), ROOT)
    if not (rel.startswith("detail/") and rel.endswith(".tex")):
        return
    try:
        cur = open(path, encoding="utf-8").read()
    except Exception:
        return
    notes = []
    body = strip_comments(cur)
    if re.search(r"\\begin\{araidashi\}", body):
        notes.append("araidashi 環境は使わない．memo/todo を直接書く．")
    notes += env_balance(body)
    old = strip_comments(head_text(rel))
    if old:
        dl = len(re.findall(r"\\label\{", body)) - len(re.findall(r"\\label\{", old))
        if dl > 0:
            notes.append(f"\\label が HEAD より {dl} 個増えている．ラベルを増やさない方針（latex-conventions.md）．参照に本当に必要か確認．")
        dt = len(re.findall(r"\\begin\{(tabular|longtable|tabularx)\}", body)) - len(re.findall(r"\\begin\{(tabular|longtable|tabularx)\}", old))
        if dt > 0:
            notes.append(f"表が HEAD より {dt} 個増えている．表は行列比較が必要な場合に限る．一覧表で定義や例文を代用しない．")
    old_lines = set(old.splitlines())
    for i, l in enumerate(body.splitlines(), 1):
        if l in old_lines:
            continue
        if "暫定" in l and not re.search(r"20\d\d-\d\d-\d\d", l) and not re.search(r"\\(memo|todo|remark)", l):
            notes.append(f"L{i}: 「暫定」に日付がない（本文に入れた暫定決定には日付を付ける）．")
            break
    ai = [i for i, l in enumerate(body.splitlines(), 1) if re.search(r"\\(aitodo|aimemo)\{", l)]
    if ai:
        notes.append("aitodo/aimemo が残っている行: " + ", ".join(map(str, ai[:8])) + " ．AIへの指示は処理後に本文へ書くか memo/todo に戻す．")
    if notes:
        msg = f"[tex-lint {rel}]\n- " + "\n- ".join(notes)
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}, ensure_ascii=False))

if __name__ == "__main__":
    main()
