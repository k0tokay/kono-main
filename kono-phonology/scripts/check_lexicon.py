#!/usr/bin/env python3
"""語彙と宣言済み制約表の齟齬を洗い出す.

- トークン化・音節化できない語
- 結合表（ω/ν/κ）に無い組み合わせを含む語
- hard 制約に違反する語
- アクセント資料の場合: F/R の 2μ 要件を満たさない音節（重さスケール別）

「表にはこう書いたが語彙は従っていない」を可視化するのが目的．
tex を直すか語彙を直すかは人間が決める．

    python3 scripts/check_lexicon.py ../kono-dictionary-editor/src/data/konomeno-v5.json
    python3 scripts/check_lexicon.py ../accent/data.tsv
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from konophon import Grammar, inventory  # noqa: E402
from konophon.corpus import autoload  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", type=Path)
    ap.add_argument("--scales", default="rime,onset_sensitive")
    a = ap.parse_args(argv)

    inv = inventory()
    c = autoload(a.path, inv)
    g = Grammar.from_inventory(inv)
    print(c.report())
    print()

    notes = [(w.spell, w.syllabified, w.notes) for w in c if w.notes]
    print(f"■ 結合表に無い組み合わせを含む語: {len(notes)}")
    tally = Counter()
    for spell, syl, ns in notes:
        for n in ns:
            tally[n.split(" ", 1)[-1]] += 1
        print(f"   {spell:16s} {syl:20s} {'; '.join(ns)}")
    if tally:
        print("   -- 集計 --")
        for k, v in tally.most_common():
            print(f"   {v:3d}  {k}")
    print()

    hard = [c_ for c_ in g if c_.is_hard]
    print(f"■ hard 制約違反 ({len(hard)} 制約)")
    for con in hard:
        bad = [w for w in c if con.violations(w)]
        print(f"   {con.name} ({con.pattern}): {len(bad)} 語 {[w.spell for w in bad][:10]}")
    print()

    accented = [w for w in c if w.accent is not None]
    if accented:
        print(f"■ 輪郭調 (F/R) の 2μ 要件（{len(accented)} 語）")
        for sc in a.scales.split(","):
            probs = [(w, w.contour_problems(sc)) for w in accented]
            n = sum(len(p) for _, p in probs)
            print(f"   [{sc}] 違反 {n} 件")
            for w, p in probs:
                for line in p:
                    print(f"        {w.spell:14s} {w.syllabified:18s} {w.accent}  {line}")
        print()
        # F のみ
        from konophon.prosody import get_scale

        print("   -- F のみ（R は発話末境界上昇の可能性があるので分離） --")
        for sc in a.scales.split(","):
            s = get_scale(sc, inv)
            n = sum(
                1
                for w in accented
                for syl, ac in zip(w.syllables, w.accent)
                if ac == "F" and s.licensing_mora(syl) < 2
            )
            print(f"   [{sc}] F の違反 {n} 件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
