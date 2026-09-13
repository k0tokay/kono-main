#!/usr/bin/env python3
"""有効本文の行範囲を出す．\\iffalse…\\fi と \\if0…\\fi の内側（入れ子対応）を無効として除く．
使い方: python3 .claude/scripts/active-lines.py <file.tex> [--inactive]
  既定：有効な行範囲と行数を出す．--inactive：無効な行範囲を出す．
コメント行（% 始まり）は無効に含めない（LaTeX 上は無視されるが，編集指示や @issue が載るため）．
"""
import re, sys

def ranges(path):
    depth = 0; act = []; inact = []
    for i, line in enumerate(open(path, encoding="utf-8"), 1):
        s = re.sub(r"(?<!\\)%.*", "", line)
        toks = re.findall(r"\\(iffalse|if0|ifnum|ifx|ifdim|ifcase|ifdefined|ifcsname|ifmmode|else|fi)\b", s)
        opened_here = depth == 0 and any(t in ("iffalse", "if0") for t in toks)
        for t in toks:
            if t in ("iffalse", "if0"):
                depth += 1 if depth > 0 or t in ("iffalse", "if0") else 0
            elif t.startswith("if"):
                if depth > 0: depth += 1   # 無効領域内の入れ子 \if…\fi を数える
            elif t == "fi":
                if depth > 0: depth -= 1
        (inact if (depth > 0 or opened_here) else act).append(i)
    def comp(lines):
        out = []
        for n in lines:
            if out and out[-1][1] == n - 1: out[-1][1] = n
            else: out.append([n, n])
        return out
    return comp(act), comp(inact), i

if __name__ == "__main__":
    if len(sys.argv) < 2: print(__doc__); sys.exit(1)
    act, inact, total = ranges(sys.argv[1])
    show = inact if "--inactive" in sys.argv else act
    label = "無効" if "--inactive" in sys.argv else "有効"
    n = sum(b - a + 1 for a, b in show)
    print(f"{sys.argv[1]}: 全{total}行，{label}{n}行： " + " ".join(f"{a}-{b}" if a != b else str(a) for a, b in show))
