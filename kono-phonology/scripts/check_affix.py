#!/usr/bin/env python3
"""接辞を語幹に付けたときの活用を検査する.

母音結合 ``+`` と子音結合 ``⊕``（``phonology.tex``「活用」節）の両方で接辞を
付け、結果を音節化・IPA・制約違反まで展開する。接辞どうしを比べるための集計も
出す：

- **語幹保存率**：結合後も語幹の音素列がそのまま先頭に残る語の割合。
- **異形態**：実際に語末へ付いた音素列の種類。1種類なら語幹によらず同じ形で付く。

「接続が自然な接辞」を、語幹を削らず・異形態を増やさないこと、と読み替えて数える。
どちらの結合を正とするか、異形態をいくつまで許すかは人間が決める。

    python3 scripts/check_affix.py ykof kof
    python3 scripts/check_affix.py ykof kof --stem komatci
    python3 scripts/check_affix.py ykof kof --lexicon ../kono-dictionary-editor/src/data/konomeno-v5.json
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from konophon import Grammar, Seq, Word, inventory  # noqa: E402
from konophon.corpus import autoload  # noqa: E402

# 語末の音素クラスを一通り踏む既定の語幹。komatci は tc + i で口蓋化と
# 母音融合の両方に掛かるため先頭に置く。
DEFAULT_STEMS = [
    "komatci",   # -i
    "waka",      # -a
    "coto",      # -o
    "meide",     # -e
    "alkono",    # -o（3音節）
    "kalam",     # -m
    "hamin",     # -n
    "meacc",     # -cc
    "klant",     # -nt
    "suinof",    # -f
    "konstav",   # -v
    "litoi",     # -oi（二重母音）
]

JOINS = [("+", "vplus"), ("⊕", "cplus")]


def attach(stem: str, affix: str, method: str, inv) -> str:
    return getattr(Seq.of(stem, inv), method)(affix).spell


def seam(stem: str, affix: str, result: str, inv):
    """(語幹が保存されたか, 実際に付いた部分, 接辞が保存されたか) を返す."""
    st = [p.spell for p in inv.tokenize(stem)]
    af = [p.spell for p in inv.tokenize(affix)]
    rs = [p.spell for p in inv.tokenize(result)]
    stem_kept = rs[: len(st)] == st
    affix_kept = rs[-len(af):] == af
    added = "".join(rs[len(st):]) if stem_kept else None
    return stem_kept, added, affix_kept


def describe(stem: str, affix: str, result: str, inv, grammar) -> str:
    stem_kept, added, affix_kept = seam(stem, affix, result, inv)
    if not stem_kept:
        note = "語幹が改変"
    elif added == affix:
        note = "無変化"
    elif affix_kept:
        note = f"挿入 -{added}"
    else:
        note = f"融合 -{added}"
    try:
        w = Word(result, inv=inv)
    except Exception as e:  # 音節化できない
        return f"{result:20s} !! {e}"
    bad = [c.name for c in grammar if c.is_hard and c.violations(w)]
    tail = f"  違反:{','.join(bad)}" if bad else ""
    tail += f"  表外:{';'.join(w.notes)}" if w.notes else ""
    return f"{result:20s} {w.syllabified:22s} {w.ipa:20s} {note}{tail}"


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("affixes", nargs="+", help="検査する接辞（綴り、先頭の + は不要）")
    ap.add_argument("--stem", action="append", default=None, help="語幹（繰り返し可）")
    ap.add_argument("--lexicon", type=Path, default=None,
                    help="語幹を実語彙から取る（konomeno-v5.json など）")
    ap.add_argument("--limit", type=int, default=400, help="--lexicon 使用時の語数上限")
    a = ap.parse_args(argv)

    inv = inventory()
    grammar = Grammar.from_inventory(inv)
    focus = a.stem or DEFAULT_STEMS[:1]
    stems = a.stem or DEFAULT_STEMS
    if a.lexicon:
        corpus = autoload(a.lexicon, inv)
        stems = []
        for w in corpus:
            if len(stems) >= a.limit:
                break
            stems.append(w.spell)

    print("■ 注目語幹")
    for stem in focus:
        for affix in a.affixes:
            for sym, method in JOINS:
                r = attach(stem, affix, method, inv)
                print(f"   {stem} {sym} {affix:6s} = {describe(stem, affix, r, inv, grammar)}")
        print()

    print("■ 語幹一覧")
    for affix in a.affixes:
        for sym, method in JOINS:
            print(f"   -- {sym} {affix} --")
            for stem in (stems if not a.lexicon else stems[:20]):
                r = attach(stem, affix, method, inv)
                print(f"      {stem:12s} -> {describe(stem, affix, r, inv, grammar)}")
        print()

    print(f"■ 集計（語幹 {len(stems)} 語）")
    for affix in a.affixes:
        for sym, method in JOINS:
            kept = 0
            allo = Counter()
            broken = []
            broken_by_final = Counter()
            bad = 0
            for stem in stems:
                try:
                    r = attach(stem, affix, method, inv)
                except Exception:
                    continue
                stem_kept, added, _ = seam(stem, affix, r, inv)
                if stem_kept:
                    kept += 1
                    allo[added] += 1
                else:
                    broken.append(stem)
                    broken_by_final[inv.tokenize(stem)[-1].spell] += 1
                try:
                    w = Word(r, inv=inv)
                    before = {c.name for c in grammar
                              if c.is_hard and c.violations(Word(stem, inv=inv))}
                except Exception:
                    bad += 1
                    continue
                after = {c.name for c in grammar if c.is_hard and c.violations(w)}
                if after - before:  # 語幹が元から持つ違反は数えない
                    bad += 1
            n = len(stems)
            print(f"   {sym} {affix:6s} 語幹保存 {kept:4d}/{n} ({kept / n:5.1%})"
                  f"  異形態 {len(allo):2d} 種 {[k for k, _ in allo.most_common(6)]}"
                  f"  結合で増えた hard違反 {bad}")
            if broken:
                by_final = " ".join(f"-{k}:{v}" for k, v in broken_by_final.most_common())
                print(f"          語幹が改変される語 {len(broken)}: 語幹末 {by_final}")
                print(f"          例: {broken[:8]}{' …' if len(broken) > 8 else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
