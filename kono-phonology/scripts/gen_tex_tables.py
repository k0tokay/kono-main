#!/usr/bin/env python3
"""phonology.toml から phonology.tex の表を生成する.

手書きの表とコードの定義が食い違うのを防ぐため、表は必ずここから出す．

    python3 scripts/gen_tex_tables.py                     # 標準出力
    python3 scripts/gen_tex_tables.py -o generated/tables.tex
    python3 scripts/gen_tex_tables.py --check ../detail/chapters/p-side/phonology.tex
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from konophon import inventory  # noqa: E402
from konophon.texgen import all_tables  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", type=Path, default=None)
    ap.add_argument("--check", type=Path, default=None, help="既存 tex と ○ の位置を突き合わせる")
    a = ap.parse_args(argv)

    inv = inventory()
    text = all_tables(inv)

    if a.check:
        src = a.check.read_text(encoding="utf-8")
        gen_marks = len(re.findall("○", text))
        src_marks = len(re.findall("○", src))
        print(f"生成された表の ○ の数: {gen_marks}")
        print(f"{a.check} の ○ の数: {src_marks}")
        print("→ 一致しない場合、toml と tex のどちらかが古い" if gen_marks != src_marks else "→ 個数は一致")
        return 0

    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text, encoding="utf-8")
        print(f"[出力] {a.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
