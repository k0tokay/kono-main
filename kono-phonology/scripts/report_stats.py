#!/usr/bin/env python3
"""遷移行列・エントロピー・相互情報量・PMI・ギャップを一括で出す.

tier を指定すると、そのレベルでの統計をすべて出力する．
``--all`` で主要な tier を横断比較（どのレベルに構造があるかが分かる）．

    python3 scripts/report_stats.py DICT --all
    python3 scripts/report_stats.py DICT --tier syllable_shape --pmi --gaps
    python3 scripts/report_stats.py ../accent/data.tsv --cooccur weight,accent
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from konophon import NgramModel, Tiers, chi2_independence, cooccurrence, inventory  # noqa: E402
from konophon.corpus import autoload  # noqa: E402
from konophon.stats import positional_distribution, tier_distribution  # noqa: E402

MAIN_TIERS = [
    "phoneme",
    "natural_class",
    "manner",
    "place",
    "syllable_shape",
    "onset_shape",
    "coda_shape",
    "weight",
]


def get_tier(t: Tiers, name: str):
    if name == "weight":
        return t.weight("rime")
    if name == "weight_os":
        return t.weight("onset_sensitive")
    if name == "mora":
        return t.mora("rime")
    if name.startswith("feature:"):
        return t.feature(name.split(":", 1)[1])
    return getattr(t, name)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", type=Path)
    ap.add_argument("--tier", default="phoneme")
    ap.add_argument("--n", type=int, default=2)
    ap.add_argument("--all", action="store_true", help="主要 tier を横断比較")
    ap.add_argument("--pmi", action="store_true")
    ap.add_argument("--gaps", action="store_true")
    ap.add_argument("--matrix", action="store_true", help="遷移行列を表示")
    ap.add_argument("--cooccur", default="", help="'weight,accent' のように 2 tier を指定")
    ap.add_argument("--out", type=Path, default=None, help="TSV 出力先ディレクトリ")
    a = ap.parse_args(argv)

    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 200)

    inv = inventory()
    c = autoload(a.path, inv)
    t = Tiers(inv)
    print(c.report().splitlines()[0])
    print()

    if a.all:
        rows = []
        for name in MAIN_TIERS:
            ng = NgramModel.build(c, get_tier(t, name), n=a.n)
            rows.append({"tier": name, **{k: v for k, v in ng.summary().items() if k != "tier"}})
        df = pd.DataFrame(rows)
        print("■ tier 横断比較（I が大きいほど、そのレベルに配列上の構造がある）")
        print(df.to_string(index=False))
        if a.out:
            a.out.mkdir(parents=True, exist_ok=True)
            df.to_csv(a.out / "tier_comparison.tsv", sep="\t", index=False)
        return 0

    tier = get_tier(t, a.tier)
    ng = NgramModel.build(c, tier, n=a.n)
    print(f"■ {a.tier} ({a.n}-gram)")
    for k, v in ng.summary().items():
        print(f"   {k:14s} {v}")
    print()

    print("■ 分布")
    print(tier_distribution(c, tier).head(25).to_string(index=False))
    print()

    print("■ 位置別分布（末尾から）")
    print(positional_distribution(c, tier, from_end=True).head(20).to_string(index=False))
    print()

    if a.matrix:
        print("■ 遷移行列 P(y|x)")
        print(ng.transition_matrix().round(3).to_string())
        print()
    if a.pmi:
        print("■ PMI")
        print(ng.pmi_matrix(min_count=2).round(2).to_string())
        print()
    if a.gaps:
        print("■ ギャップ（期待値が高いのに出現ゼロ ＝ 制約候補）")
        print(ng.gaps(min_expected=1.0).head(30).to_string(index=False))
        print()

    if a.cooccur:
        x, y = [s.strip() for s in a.cooccur.split(",")]
        tab = cooccurrence(c, get_tier(t, x), get_tier(t, y))
        print(f"■ 共起表 {x} × {y}")
        print(tab.to_string())
        st = chi2_independence(tab)
        print(f"   chi2={st['chi2']:.3f} p={st['p']:.4g} Cramér's V={st['cramers_v']:.3f}")

    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
        ng.transition_matrix().to_csv(a.out / f"transition_{a.tier}.tsv", sep="\t")
        ng.pmi_matrix().to_csv(a.out / f"pmi_{a.tier}.tsv", sep="\t")
        print(f"\n[出力] {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
