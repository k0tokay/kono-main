#!/usr/bin/env python3
"""公開版を作る．開発版（HEAD）から，.tex のコメントと無効領域を落とした木を組み，ローカルの public ブランチに1コミット積む．
push はしない（作者が `git push origin public:main` を別に実行する）．

使い方: python3 .claude/scripts/publish.py [--no-verify] [--dry-run]
  既定：追跡ファイルだけを HEAD から取り出し → .tex を整形 → 公開版と開発版を両方ビルドして文字の出現数が一致するか確認
        → public ブランチ（無ければ origin/main から作る）へコミット．
  --no-verify  ビルド照合を省く．  --dry-run  整形した木を作るだけでコミットしない（木の場所を表示）．

除外処理（.tex）：
  - `%` 以降のコメント．行頭のコメント行は行ごと消す．行末コメントは `%` だけ残す（改行の吸収を保つ）．
  - \\iffalse…\\fi と \\if0…\\fi の内側（入れ子対応．\\newif で作った名前を含む任意の \\ifXXX を数える）．内側に \\else があれば中止する．
  - verbatim 系の環境と \\verb の中の `%` は触らない．
新しい除外処理は sanitize_tex の後ろに足す．公開してよいかの判断（何を落とすか）は作者が決める．
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())

LEAK = re.compile(r"chatgpt\.com/(c|g)/|chat\.openai\.com/c/|claude\.ai/chat/|gemini\.google\.com/app/")
VERB_ENVS = ("verbatim", "lstlisting", "minted", "Verbatim")


def sh(*args, cwd=ROOT, check=True):
    return subprocess.run(args, cwd=cwd, check=check, text=True, capture_output=True)


def strip_comment(line, in_verb_env):
    """1行からコメントを除く．戻り値 (整形後の行 or None（行ごと削除）)．"""
    if in_verb_env:
        return line
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if c == "\\":
            if line.startswith("\\verb", i) and i + 5 < n and not line[i + 5].isalpha():
                d = line[i + 5]
                j = line.find(d, i + 6)
                i = (j + 1) if j != -1 else n
                continue
            i += 2
            continue
        if c == "%":
            head = line[:i]
            if head.strip() == "":
                return None
            return head.rstrip() + "%\n" if line.endswith("\n") else head.rstrip() + "%"
        i += 1
    return line


# 値で分岐するだけで \fi を持たない etoolbox 系などの名前（無効領域の中で入れ子として数えない）
NOT_CONDITIONAL = {"iff", "ifthenelse", "ifdef", "ifundef", "ifcsdef", "ifcsundef", "ifdefempty", "ifcsempty",
                   "ifdefvoid", "ifcsvoid", "ifdefequal", "ifcsequal", "ifdefstring", "ifcsstring", "ifdefstrequal",
                   "ifstrequal", "ifstrempty", "ifblank", "ifnumcomp", "ifnumequal", "ifnumgreater", "ifnumless",
                   "ifdimcomp", "ifdimequal", "ifdimgreater", "ifdimless", "ifbool", "iftoggle", "ifboolexpr",
                   "ifltxcounter", "ifinlist"}
TOKEN = re.compile(r"\\(newif\s*\\if[A-Za-z@]+|if[A-Za-z@]*|else|fi)(?![A-Za-z@])")


def dead_lines(text, name):
    """\\iffalse／\\if0 から対応する \\fi までの行番号の集合（入れ子対応，任意の \\ifXXX を数える）．"""
    dead, depth, start = set(), 0, 0
    for no, line in enumerate(text.splitlines(), 1):
        body = re.sub(r"(?<!\\)%.*", "", line)
        for m in TOKEN.finditer(body):
            t = m.group(1)
            if t.startswith("newif"):
                continue
            if depth == 0:
                if t in ("iffalse", "if0"):
                    if body[:m.start()].strip():
                        raise SystemExit(f"中止：{name}:{no} \\{t} の前に同じ行の内容がある．")
                    depth, start = 1, no
                continue
            if t == "else" and depth == 1:
                raise SystemExit(f"中止：{name}:{no} 無効領域（{start} 行〜）の内側に \\else がある（else 側は有効かもしれない）．")
            if t.startswith("if") and t not in NOT_CONDITIONAL:
                depth += 1
            elif t == "fi":
                depth -= 1
                if depth == 0:
                    if body[m.end():].strip():
                        raise SystemExit(f"中止：{name}:{no} 閉じの \\fi の後ろに同じ行の内容がある．")
                    dead.update(range(start, no + 1))
        if depth > 0:
            dead.add(no)
    if depth != 0:
        raise SystemExit(f"中止：{name} の \\iffalse／\\if0 が閉じていない（{start} 行〜）．")
    return dead


def sanitize_tex(path):
    text = path.read_text(encoding="utf-8")
    dead = dead_lines(text, str(path.name))
    out, verb = [], None
    for no, line in enumerate(text.splitlines(keepends=True), 1):
        if no in dead:
            body = re.sub(r"(?<!\\)%.*", "", line)
            if re.search(r"\\else\b", body):
                raise SystemExit(f"中止：{path} の {no} 行，無効領域の内側に \\else がある（else 側は有効かもしれない）．")
            continue
        m = re.search(r"\\begin\{(%s)\*?\}" % "|".join(VERB_ENVS), line)
        in_verb = verb is not None
        if m and verb is None:
            verb = m.group(1)
        new = strip_comment(line, in_verb)
        if verb is not None and re.search(r"\\end\{%s\*?\}" % verb, line):
            verb = None
        if new is not None:
            out.append(new)
    # コメント行を消した結果できた3行以上の連続空行を2行に詰める（段落区切りは保つ）
    res = re.sub(r"\n{3,}", "\n\n", "".join(out))
    path.write_text(res, encoding="utf-8")


def build_pdf_text(tree):
    d = tree / "detail"
    for _ in range(2):
        r = subprocess.run(["lualatex", "-interaction=nonstopmode", "-halt-on-error", "main-detail.tex"],
                           cwd=d, text=True, capture_output=True)
        if r.returncode != 0:
            raise SystemExit(f"中止：{tree} のビルドに失敗．\n" + r.stdout[-1500:])
    txt = subprocess.check_output(["pdftotext", str(d / "main-detail.pdf"), "-"], text=True)
    # 欄外のソース行番号・ファイル名:行番号の注記はコメント除去で変わる．改行位置も変わりうるので空白を除いて比べる
    txt = "\n".join(ln for ln in txt.splitlines() if not re.fullmatch(r"\d+", ln.strip()))
    txt = re.sub(r"[A-Za-z][\w-]*:\d+", "", txt)
    # pdftotext は数式の上付き・下付きの出力順が揺れるので，文字の多重集合で比べる
    return "".join(sorted(re.sub(r"\s+", "", txt)))


def main():
    verify = "--no-verify" not in sys.argv
    dry = "--dry-run" in sys.argv
    if sh("git", "status", "--porcelain", "--untracked-files=no").stdout.strip():
        raise SystemExit("中止：追跡ファイルに未コミットの変更がある．先にコミットする．")
    head = sh("git", "rev-parse", "--short", "HEAD").stdout.strip()
    work = Path(tempfile.mkdtemp(prefix="kono-publish-"))
    pub, dev = work / "public", work / "dev"
    for d in (pub, dev):
        d.mkdir()
        arc = subprocess.Popen(["git", "archive", "HEAD"], cwd=ROOT, stdout=subprocess.PIPE)
        subprocess.run(["tar", "-x", "-C", str(d)], stdin=arc.stdout, check=True)
        arc.wait()
    n = 0
    for p in pub.rglob("*.tex"):
        if p.is_symlink():
            continue
        sanitize_tex(p)
        n += 1
    print(f"[publish] {n} 個の .tex を整形した（基準 {head}）．")

    leaks = []
    for p in pub.rglob("*"):
        if p.is_file() and not p.is_symlink():
            try:
                for no, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                    if LEAK.search(ln):
                        leaks.append(f"{p.relative_to(pub)}:{no}")
            except UnicodeDecodeError:
                pass
    if leaks:
        raise SystemExit("中止：チャットのリンクが残っている：\n  " + "\n  ".join(leaks[:20]))

    if verify:
        a, b = build_pdf_text(dev), build_pdf_text(pub)
        if a != b:
            ca, cb = Counter(a), Counter(b)
            raise SystemExit(f"中止：開発版と公開版で文字の出現数が違う．\n開発版にだけ: {dict(ca - cb)}\n公開版にだけ: {dict(cb - ca)}")
        print("[publish] 照合：開発版と公開版で文字の出現数が一致（行番号の注記は除く）．")
        for t in (pub, dev):
            for ext in ("aux", "log", "out", "toc", "pdf", "synctex.gz", "bbl", "blg"):
                for f in (t / "detail").rglob(f"*.{ext}"):
                    f.unlink()

    if dry:
        print(f"[publish] dry-run：整形した木は {pub}")
        return
    wt = work / "wt"
    have = sh("git", "rev-parse", "--verify", "-q", "refs/heads/public", check=False).returncode == 0
    if have:
        sh("git", "worktree", "add", str(wt), "public")
    else:
        sh("git", "worktree", "add", "-b", "public", str(wt), "origin/main")
    try:
        sh("git", "rm", "-r", "-q", "--ignore-unmatch", ".", cwd=wt)
        for child in wt.iterdir():
            if child.name != ".git":
                shutil.rmtree(child) if child.is_dir() and not child.is_symlink() else child.unlink()
        for child in pub.iterdir():
            dst = wt / child.name
            if child.is_symlink():
                os.symlink(os.readlink(child), dst)
            elif child.is_dir():
                shutil.copytree(child, dst, symlinks=True)
            else:
                shutil.copy2(child, dst, follow_symlinks=False)
        sh("git", "add", "-A", cwd=wt)
        if not sh("git", "diff", "--cached", "--name-only", cwd=wt).stdout.strip():
            print("[publish] 公開版に変更なし．")
        else:
            sh("git", "commit", "-q", "-m", f"公開版：開発版 {head} から生成（.tex のコメントと無効領域を除去）", cwd=wt)
            print("[publish] public ブランチにコミット：", sh("git", "log", "--oneline", "-1", cwd=wt).stdout.strip())
            print("[publish] 公開するには： git push origin public:main")
    finally:
        sh("git", "worktree", "remove", "--force", str(wt), check=False)
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
