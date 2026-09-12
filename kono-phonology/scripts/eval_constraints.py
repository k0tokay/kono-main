#!/usr/bin/env python3
"""音韻規則候補の「尤度」を評価する.

候補は DSL で書いた markedness 制約として渡す．コマンドラインで直接
書くか、1行1制約のファイルで渡す（``#`` はコメント、``名前 TAB パターン``
の形も可）．

    python3 scripts/eval_constraints.py DICT '*[C][C][C][C]' '*[N][N]'
    python3 scripts/eval_constraints.py DICT --file candidates.txt --fit
    python3 scripts/eval_constraints.py DICT --discover --top 30

出力の読み方:

O/E
    観測違反数 / baseline 下の期待違反数．1 より十分小さければ回避されている
p
    違反を含む語の割合についての二項検定
dLL
    その制約を文法に足したときの対数尤度の改善．**候補間の比較はこれで行う**

baseline のモード（``--baseline``）:

``cv``        CV 骨格の分布を保ったまま各位置を C/V 内でランダム化
              → 骨格を説明変数から外し「どの子音がどこに来るか」だけを見る
``unigram``   音素頻度と語長分布だけを保つ → 骨格レベルの制約も検出できる
``positional`` 語頭・語中・語末で別々の unigram
"""

from __future__ import annotations

import argparse
import sys
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from konophon import Baseline, Constraint, Grammar, evaluate_many, inventory  # noqa: E402
from konophon.corpus import autoload  # noqa: E402


def read_candidate_file(path: Path) -> list[Constraint]:
    """1行1制約．``名前<TAB>パターン[<TAB>tier]`` の形も可．

    ``#`` は語境界記号でもあるので、行頭または空白の直後に来たときだけ
    コメントとみなす．
    """
    import re

    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = re.split(r"(?:^|\s)#", raw)[0].strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("\t") if p.strip()]
        if len(parts) == 1:
            out.append(Constraint(parts[0]))
        elif len(parts) == 2:
            out.append(Constraint(parts[1], parts[0]))
        else:
            out.append(Constraint(parts[1], parts[0], tier=parts[2]))
    return out


def discover(inv, tiers=("segment",)) -> list[Constraint]:
    """自然類の 2-gram / 3-gram を機械的に列挙して候補にする."""
    cls = ["S", "Q", "T", "N", "L", "J", "V"]
    out = [Constraint(f"*[{a}][{b}]", f"*{a}{b}") for a, b in product(cls, repeat=2)]
    out += [Constraint(f"*#[{a}][{b}]", f"*#{a}{b}") for a, b in product(cls, repeat=2)]
    out += [Constraint(f"*[{a}][{b}]#", f"*{a}{b}#") for a, b in product(cls, repeat=2)]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", type=Path, help="語彙")
    ap.add_argument("patterns", nargs="*", help="DSL の制約パターン")
    ap.add_argument("--file", type=Path, default=None)
    ap.add_argument("--discover", action="store_true", help="自然類 bigram を機械的に列挙")
    ap.add_argument("--baseline", default="cv", choices=["cv", "unigram", "positional"])
    ap.add_argument("--samples", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--fit", action="store_true", help="MaxEnt で重みを同時推定する")
    ap.add_argument(
        "--syllabifiable",
        action="store_true",
        help="baseline を音節化できる語だけに絞る（syllable tier の制約を評価するとき必須）",
    )
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)

    pd.set_option("display.width", 240)
    pd.set_option("display.max_rows", 400)

    inv = inventory()
    c = autoload(a.path, inv)
    words = list(c)
    print(f"[語彙] {len(words)} 語")

    cands: list[Constraint] = [Constraint(p) for p in a.patterns]
    if a.file:
        cands += read_candidate_file(a.file)
    if a.discover:
        cands += discover(inv)
    if not cands:
        cands = [Constraint(d["pattern"], d.get("name", "")) for d in inv.declared_constraints]
        print("[候補] phonology.toml の宣言済み制約を評価します")

    bl = Baseline.fit(words, mode=a.baseline, require_syllabifiable=a.syllabifiable)
    samples = bl.sample(a.samples, np.random.default_rng(a.seed))
    print(f"[baseline] mode={a.baseline} sample={len(samples)}  例: {[w.spell for w in samples[:6]]}")
    print()

    df = evaluate_many(cands, words, samples)
    print(df.head(a.top).to_string(index=False))

    if a.fit:
        soft = [c_ for c_ in cands if not c_.is_hard]
        g = Grammar(soft, inv)
        res = g.fit(words, samples, l2=0.5)
        print("\n■ MaxEnt 同時推定（重みが大きいほど強く効いている）")
        print(res.table().head(a.top).to_string(index=False))
        print(f"   NLL={res.nll:.4f}  iter={res.n_iter}")

    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(a.out, sep="\t", index=False)
        print(f"\n[出力] {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
