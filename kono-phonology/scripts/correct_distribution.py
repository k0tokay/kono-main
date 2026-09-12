"""分布矯正の試作: 書き換え規則を辞書全体へ適用し，前後の分布と衝突を報告する.

使い方:
  python3 scripts/correct_distribution.py ../kono-dictionary-editor/src/data/konomeno-v5.json \
      --rules correction/rules.toml --out out/correction
出力:
  changes.tsv        変更された語（元 / 結果 / 適用規則）
  after.words.txt    矯正後の綴り（1行1語）
  after.ipa.txt      矯正後の IPA セグメント列（typology/compare_dist.py の --extra 用）
  report.md          規則ごとの適用数，衝突，前後の分布指標
"""
from __future__ import annotations

import argparse
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "typology"))

from konophon import Word  # noqa: E402
from konophon.corpus import autoload  # noqa: E402
from konophon.rewrite import RuleSet, derive  # noqa: E402
from kono_ipa import CONSONANT_IPA, VOWEL_IPA  # noqa: E402

IPA = {**CONSONANT_IPA, **VOWEL_IPA}
VOICED = {"b", "d", "g", "z", "zc"}
VOICELESS = {"p", "t", "k", "s", "c", "f", "h", "kh", "ts", "tc"}
SONORANT_C = {"m", "n", "ng", "l", "w", "j"}


def metrics(words: list[Word]) -> dict:
    c = Counter(p.spell for w in words for p in w.seq)
    tot = sum(c.values())
    freqs = sorted(c.values(), reverse=True)
    H = -sum(n / tot * math.log2(n / tot) for n in freqs)
    obst = sum(c[x] for x in VOICED | VOICELESS)
    cons = sum(c[x] for x in VOICED | VOICELESS | SONORANT_C)
    shapes = Counter(s.shape for w in words for s in w.syllables)
    ns = sum(shapes.values())
    return {
        "top10": sum(freqs[:10]) / tot,
        "H_rel": H / math.log2(len(freqs)),
        "voiced/obstruent": sum(c[x] for x in VOICED) / obst,
        "sonorant/C": sum(c[x] for x in SONORANT_C) / cons,
        "a+o share of V": (c["a"] + c["o"]) / (tot - cons),
        "u+v share of V": (c["u"] + c["v"]) / (tot - cons),
        "closed syl": sum(n for s, n in shapes.items() if s.endswith("C")) / ns,
        "V-initial syl": sum(n for s, n in shapes.items() if s.startswith("V")) / ns,
        "_counts": c,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lexicon")
    ap.add_argument("--rules", default=str(BASE / "correction" / "rules.toml"))
    ap.add_argument("--out", default=str(BASE / "out" / "correction"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    rules = RuleSet.from_toml(a.rules)
    before = list(autoload(a.lexicon))
    derivs = [derive(w.spell, rules) for w in before]
    after_words, bad = [], []
    for d in derivs:
        w = Word.try_make(d.result)
        if w is None:
            bad.append(d)
            w = Word(d.source)
        after_words.append(w)

    # 規則ごとの適用数
    per_rule = Counter()
    for d in derivs:
        for name, _ in d.steps:
            per_rule[name] += 1
    # 衝突: 結果が同じ綴りになった語
    by_result = defaultdict(list)
    for d in derivs:
        by_result[d.result].append(d.source)
    collisions = {k: v for k, v in by_result.items() if len(v) > 1}

    mb, ma = metrics(before), metrics(after_words)
    lines = ["# 分布矯正レポート", "", f"規則: `{a.rules}`", f"語数: {len(before)}, 変更: {sum(d.changed for d in derivs)}", ""]
    lines += ["## 規則ごとの適用語数", "", "| 規則 | 語数 |", "|---|---|"]
    for name, _ in rules.rules:
        if name in per_rule or True:
            pass
    seen = set()
    for name, _ in rules.rules:
        if name in seen:
            continue
        seen.add(name)
        lines.append(f"| {name} | {per_rule.get(name, 0)} |")
    lines += ["", f"## 衝突（同綴りに合流）: {len(collisions)} 組", ""]
    for k, v in sorted(collisions.items()):
        lines.append(f"- `{k}` ← " + ", ".join(f"`{s}`" for s in v))
    if bad:
        lines += ["", f"## 音素列として解釈できない結果: {len(bad)}", ""]
        lines += [f"- `{d.source}` → `{d.result}`" for d in bad]
    lines += ["", "## 指標（前 → 後）", "", "| 指標 | 前 | 後 |", "|---|---|---|"]
    for k in mb:
        if k.startswith("_"):
            continue
        lines.append(f"| {k} | {mb[k]:.3f} | {ma[k]:.3f} |")
    lines += ["", "## 音素頻度（前 → 後）", "", "| 音素 | 前 | 前% | 後 | 後% | 順位(前→後) |", "|---|---|---|---|---|---|"]
    cb, ca = mb["_counts"], ma["_counts"]
    tb, ta = sum(cb.values()), sum(ca.values())
    rb = {p: i for i, (p, _) in enumerate(cb.most_common(), 1)}
    ra = {p: i for i, (p, _) in enumerate(ca.most_common(), 1)}
    for p, _ in sorted(ca.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {p} | {cb[p]} | {100*cb[p]/tb:.1f} | {ca[p]} | {100*ca[p]/ta:.1f} | {rb.get(p,'-')}→{ra[p]} |")
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")

    with open(out / "changes.tsv", "w", encoding="utf-8") as f:
        f.write("source\tresult\tsteps\n")
        for d in derivs:
            if d.changed:
                f.write(f"{d.source}\t{d.result}\t" + " > ".join(f"{n}:{s}" for n, s in d.steps) + "\n")
    (out / "after.words.txt").write_text("\n".join(w.spell for w in after_words) + "\n")
    (out / "after.ipa.txt").write_text("\n".join(" ".join(IPA[p.spell] for p in w.seq) for w in after_words) + "\n")
    print(f"changed {sum(d.changed for d in derivs)}/{len(before)}, collisions {len(collisions)}, unparsable {len(bad)}")
    for k in mb:
        if not k.startswith("_"):
            print(f"  {k:18s} {mb[k]:.3f} -> {ma[k]:.3f}")


if __name__ == "__main__":
    main()
