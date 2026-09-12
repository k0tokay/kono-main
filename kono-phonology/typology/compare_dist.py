"""ランク分布の言語間比較（音素・音節型・音節・bigram・語長・クラスタ・遷移）.

参照言語は NorthEuraLex (lexibank CLDF, raw/northeuralex-forms.csv) の IPA を使う．
コノメノは konophon の Corpus から読み，kono_ipa で IPA へ写す．

使い方:
  python3 compare_dist.py                       # rus, khk, hrv, ekk vs Konomeno
  python3 compare_dist.py --langs rus khk       # 参照言語を絞る
  python3 compare_dist.py --kono path.json --tag after   # 矯正後辞書を別名で追加
出力: output/compare_dist.md, output/dist_*.png
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE.parent))
from ipa_classes import broad, cv, manner, voiced  # noqa: E402

FORMS = BASE / "raw" / "northeuralex-forms.csv"
KONO_DICT = BASE.parent.parent / "kono-dictionary-editor" / "src" / "data" / "konomeno-v5.json"
LANG_NAMES = {"rus": "Russian", "khk": "Mongolian", "hrv": "Croatian", "ekk": "Estonian", "fin": "Finnish"}


# ---------------------------------------------------------------- データ
@dataclass
class Lexicon:
    name: str
    words: list[list[str]]          # 広い IPA セグメント列
    feats: dict[str, dict] = field(default_factory=dict)   # seg -> {cv, manner, voiced}

    def __post_init__(self):
        for w in self.words:
            for s in w:
                if s not in self.feats:
                    self.feats[s] = {"cv": cv(s), "manner": manner(s), "voiced": voiced(s)}

    # -- 音節化：語頭に立てるオンセット（2回以上出現）を最大化 ----------
    def _licensed_onsets(self) -> set[tuple[str, ...]]:
        c = Counter()
        for w in self.words:
            k = 0
            while k < len(w) and self.feats[w[k]]["cv"] == "C":
                k += 1
            if 0 < k < len(w):
                c[tuple(w[:k])] += 1
        lic = {o for o, n in c.items() if n >= 2}
        lic.add(())
        return lic

    def syllabify(self, w: list[str], lic: set) -> list[list[str]]:
        idx = [i for i, s in enumerate(w) if self.feats[s]["cv"] == "V"]
        if not idx:
            return [w]
        syls = []
        start = 0
        for a, b in zip(idx, idx[1:]):
            cluster = w[a + 1:b]
            # 分割点: オンセットが最長でライセンスされる位置
            cut = 0
            for k in range(len(cluster) + 1):
                if tuple(cluster[k:]) in lic:
                    cut = k
                    break
            end = a + 1 + cut
            syls.append(w[start:end])
            start = end
        syls.append(w[start:])
        return syls

    def syllables(self) -> list[list[list[str]]]:
        lic = self._licensed_onsets()
        return [self.syllabify(w, lic) for w in self.words]

    def shape(self, syl: list[str]) -> str:
        return "".join(self.feats[s]["cv"] for s in syl)


def load_northeuralex(lang: str) -> Lexicon:
    words = []
    seen = set()
    with open(FORMS, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["Language_ID"] != lang:
                continue
            segs = [broad(s) for s in r["Segments"].split() if s not in ("+", "_", "-")]
            key = tuple(segs)
            if segs and key not in seen:
                seen.add(key)
                words.append(segs)
    return Lexicon(LANG_NAMES.get(lang, lang), words)


def load_konomeno(path: Path, name: str = "Konomeno") -> Lexicon:
    from konophon.corpus import autoload
    from kono_ipa import CONSONANT_IPA, VOWEL_IPA
    ipa = {**CONSONANT_IPA, **VOWEL_IPA}
    words = []
    for w in autoload(path):
        words.append([ipa[p.spell] for p in w.seq])
    return Lexicon(name, words)


def load_wordlist_ipa(path: Path, name: str) -> Lexicon:
    """1行1語，空白区切りの IPA セグメント列（矯正後辞書の出力用）."""
    words = [[broad(s) for s in line.split()] for line in path.read_text().splitlines() if line.strip()]
    return Lexicon(name, words)


# ---------------------------------------------------------------- 分布
def rank_stats(counter: Counter, topk: int = 10) -> dict:
    tot = sum(counter.values())
    freqs = np.array(sorted(counter.values(), reverse=True), float) / tot
    n = len(freqs)
    H = -float(np.sum(freqs * np.log2(freqs)))
    Hrel = H / math.log2(n) if n > 1 else 1.0
    ranks = np.arange(1, n + 1)
    # 幾何分布 (Macklin-Cordes & Round 2020 が全目録に対して推奨) の MLE: p = 1/E[r]
    Er = float(np.sum(ranks * freqs))
    p_geo = 1.0 / Er
    geo = (1 - p_geo) ** (ranks - 1) * p_geo
    geo /= geo.sum()
    # 対数尤度比 (トークンごと) geometric vs Yule(最小二乗)
    yule = fit_yule(ranks, freqs)
    ll_geo = float(np.sum(freqs * np.log(geo)))
    ll_yule = float(np.sum(freqs * np.log(np.clip(yule, 1e-12, None)))) if yule is not None else float("nan")
    return {
        "n_types": n,
        "n_tokens": tot,
        "top%d" % topk: float(freqs[:topk].sum()),
        "top1": float(freqs[0]),
        "H_bits": H,
        "H_rel": Hrel,
        "p_geo": p_geo,
        "ll_geo": ll_geo,
        "ll_yule": ll_yule,
        "freqs": freqs,
    }


def fit_yule(ranks, freqs):
    try:
        from scipy.optimize import curve_fit
        f = lambda r, a, b, c: (a / np.power(r, b)) * np.power(c, r)
        popt, _ = curve_fit(f, ranks, freqs, p0=[freqs[0], 0.5, 0.95],
                            bounds=([0, -2, 0.01], [10, 5, 1.0]), maxfev=20000)
        y = f(ranks, *popt)
        return y / y.sum()
    except Exception:
        return None


def dirichlet_expected(n: int, seed: int = 0, draws: int = 2000) -> np.ndarray:
    """arXiv:2603.02860 の巨視モデル: 対称 Dirichlet(α) の順序統計量, α ≈ 19.47 n^-0.95."""
    alpha = 19.47 * n ** -0.95
    rng = np.random.default_rng(seed)
    x = rng.dirichlet([alpha] * n, size=draws)
    x.sort(axis=1)
    return x[:, ::-1].mean(axis=0)


def distributions(lex: Lexicon) -> dict[str, Counter]:
    d: dict[str, Counter] = {}
    d["phoneme"] = Counter(s for w in lex.words for s in w)
    d["consonant"] = Counter(s for w in lex.words for s in w if lex.feats[s]["cv"] == "C")
    d["vowel"] = Counter(s for w in lex.words for s in w if lex.feats[s]["cv"] == "V")
    d["manner"] = Counter(lex.feats[s]["manner"] for w in lex.words for s in w)
    d["bigram"] = Counter((a, b) for w in lex.words for a, b in zip(["#"] + w, w + ["#"]))
    d["cv_bigram"] = Counter(
        (lex.feats.get(a, {"cv": "#"})["cv"], lex.feats.get(b, {"cv": "#"})["cv"])
        for w in lex.words for a, b in zip(["#"] + w, w + ["#"]))
    syls = lex.syllables()
    d["syllable"] = Counter("".join(s) for ws in syls for s in ws)
    d["syl_shape"] = Counter(lex.shape(s) for ws in syls for s in ws)
    d["word_len_seg"] = Counter(len(w) for w in lex.words)
    d["word_len_syl"] = Counter(len(ws) for ws in syls)
    # クラスタ（語中の子音連続，長さ>=2）
    cl = Counter()
    for w in lex.words:
        run = []
        for s in w + ["#"]:
            if s != "#" and lex.feats[s]["cv"] == "C":
                run.append(s)
            else:
                if len(run) >= 2:
                    cl["".join(run)] += 1
                run = []
    d["cluster"] = cl
    d["initial"] = Counter(w[0] for w in lex.words)
    d["final"] = Counter(w[-1] for w in lex.words)
    return d


def summary_ratios(lex: Lexicon) -> dict:
    segs = [s for w in lex.words for s in w]
    n = len(segs)
    nv = sum(1 for s in segs if lex.feats[s]["cv"] == "V")
    obst = [lex.feats[s]["voiced"] for s in segs if lex.feats[s]["voiced"] is not None]
    son = sum(1 for s in segs if lex.feats[s]["manner"] in ("nasal", "liquid", "approximant"))
    syls = lex.syllables()
    nsyl = sum(len(ws) for ws in syls)
    closed = sum(1 for ws in syls for s in ws if lex.shape(s).endswith("C"))
    complex_onset = sum(1 for ws in syls for s in ws if lex.shape(s).startswith("CC"))
    return {
        "words": len(lex.words),
        "V share": nv / n,
        "voiced obstruent share": (sum(obst) / len(obst)) if obst else float("nan"),
        "sonorant C share (of C)": son / (n - nv),
        "closed syl share": closed / nsyl,
        "complex onset share": complex_onset / nsyl,
        "mean seg/word": n / len(lex.words),
        "mean syl/word": nsyl / len(lex.words),
    }


def js_divergence(p: Counter, q: Counter) -> float:
    keys = set(p) | set(q)
    tp, tq = sum(p.values()), sum(q.values())
    P = np.array([p.get(k, 0) / tp for k in keys])
    Q = np.array([q.get(k, 0) / tq for k in keys])
    M = (P + Q) / 2
    kl = lambda a, b: float(np.sum(np.where(a > 0, a * np.log2(np.clip(a, 1e-300, None) / np.clip(b, 1e-300, None)), 0)))
    return 0.5 * kl(P, M) + 0.5 * kl(Q, M)


# ---------------------------------------------------------------- 出力
UNITS = [("phoneme", 10), ("consonant", 5), ("vowel", 3), ("syl_shape", 3), ("syllable", 10),
         ("bigram", 10), ("cluster", 5), ("word_len_seg", 3), ("word_len_syl", 2)]


def fmt(x, nd=3):
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def write_report(lexes: list[Lexicon], out_md: Path):
    lines = ["# ランク分布の比較", "",
             "参照: NorthEuraLex (Dellert et al. 2020) の IPA を修飾記号を落として使用．",
             "コノメノは辞書見出し語．統計量は Macklin-Cordes & Round (2020) に従い R² ではなく，",
             "相対エントロピー H/log2(n)，上位k占有率，幾何分布 MLE の p，Yule と幾何のトークン当たり対数尤度を示す．", ""]
    dists = {lx.name: distributions(lx) for lx in lexes}
    # 概況
    lines += ["## 概況", "", "| 指標 | " + " | ".join(lx.name for lx in lexes) + " |",
              "|---|" + "---|" * len(lexes)]
    sums = {lx.name: summary_ratios(lx) for lx in lexes}
    for k in next(iter(sums.values())):
        lines.append(f"| {k} | " + " | ".join(fmt(sums[lx.name][k]) for lx in lexes) + " |")
    lines.append("")
    # 単位ごと
    for unit, topk in UNITS:
        lines += [f"## {unit}", "", "| 指標 | " + " | ".join(lx.name for lx in lexes) + " |",
                  "|---|" + "---|" * len(lexes)]
        st = {lx.name: rank_stats(dists[lx.name][unit], topk) for lx in lexes}
        for k in ("n_types", "n_tokens", "top1", f"top{topk}", "H_bits", "H_rel", "p_geo", "ll_geo", "ll_yule"):
            lines.append(f"| {k} | " + " | ".join(fmt(st[lx.name][k]) for lx in lexes) + " |")
        lines.append("")
        # 上位項目
        lines.append("上位項目（相対頻度%）:")
        lines.append("")
        for lx in lexes:
            c = dists[lx.name][unit]
            tot = sum(c.values())
            items = ", ".join(f"{(''.join(k) if isinstance(k, tuple) else k)} {100*n/tot:.1f}" for k, n in c.most_common(topk + 5))
            lines.append(f"- **{lx.name}**: {items}")
        lines.append("")
    # 調音法クラスの分布と遷移
    lines += ["## 調音法クラス", ""]
    manners = ["vowel", "plosive", "fricative", "affricate", "nasal", "liquid", "approximant"]
    lines += ["| クラス | " + " | ".join(lx.name for lx in lexes) + " |", "|---|" + "---|" * len(lexes)]
    for m in manners:
        row = []
        for lx in lexes:
            c = dists[lx.name]["manner"]
            row.append(f"{100*c.get(m,0)/sum(c.values()):.1f}")
        lines.append(f"| {m} | " + " | ".join(row) + " |")
    lines.append("")
    lines += ["### クラス遷移 P(next | prev) （%）", ""]
    for lx in lexes:
        c = Counter()
        for w in lx.words:
            ms = ["#"] + [lx.feats[s]["manner"] for s in w] + ["#"]
            c.update(zip(ms, ms[1:]))
        labs = ["#"] + manners
        lines += [f"**{lx.name}**", "", "| prev\\next | " + " | ".join(labs) + " |", "|---|" + "---|" * len(labs)]
        for a in labs:
            tot = sum(c[(a, b)] for b in labs)
            if tot == 0:
                continue
            lines.append(f"| {a} | " + " | ".join(f"{100*c[(a,b)]/tot:.0f}" for b in labs) + " |")
        lines.append("")
    # コノメノとの JS 距離
    kono = [lx for lx in lexes if lx.name.startswith("Konomeno")]
    refs = [lx for lx in lexes if not lx.name.startswith("Konomeno")]
    if kono and refs:
        lines += ["## コノメノと参照言語の JS ダイバージェンス (bits)", "",
                  "| 単位 | " + " | ".join(f"{k.name} vs {r.name}" for k in kono for r in refs) + " |",
                  "|---|" + "---|" * (len(kono) * len(refs))]
        for unit in ("manner", "cv_bigram", "syl_shape", "word_len_syl", "phoneme"):
            row = [fmt(js_divergence(dists[k.name][unit], dists[r.name][unit])) for k in kono for r in refs]
            lines.append(f"| {unit} | " + " | ".join(row) + " |")
        lines.append("")
    out_md.write_text("\n".join(lines), encoding="utf-8")
    return dists


def plot(lexes, dists, out_dir: Path, stem: str = "dist_compare"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    matplotlib.rcParams["font.family"] = "Hiragino Sans"
    units = [("phoneme", "音素"), ("syl_shape", "音節型 (CV骨格)"), ("syllable", "音節"),
             ("bigram", "音素 bigram"), ("cluster", "子音クラスタ"), ("word_len_syl", "語長 (音節)")]
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    for ax, (unit, title) in zip(axes.flat, units):
        for lx in lexes:
            st = rank_stats(dists[lx.name][unit])
            r = np.arange(1, len(st["freqs"]) + 1)
            ax.plot(r, st["freqs"], marker="o", ms=3, lw=1, label=f"{lx.name} (n={st['n_types']}, H/logn={st['H_rel']:.2f})")
        if unit == "phoneme":
            for lx in lexes:
                n = dists[lx.name][unit].__len__()
            k = [lx for lx in lexes if lx.name.startswith("Konomeno")]
            if k:
                n = len(dists[k[0].name][unit])
                ax.plot(np.arange(1, n + 1), dirichlet_expected(n), "k--", lw=1, label=f"Dirichlet 期待値 (n={n})")
        ax.set_yscale("log")
        if unit in ("syllable", "bigram", "cluster"):
            ax.set_xscale("log")
        ax.set_title(title)
        ax.set_xlabel("rank")
        ax.set_ylabel("相対頻度")
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / (stem + ".png"), dpi=130)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--langs", nargs="*", default=["rus", "khk", "hrv", "ekk"])
    ap.add_argument("--kono", default=str(KONO_DICT))
    ap.add_argument("--extra", nargs="*", default=[], help="name=path.ipa.txt（矯正後など）")
    ap.add_argument("--out", default=str(BASE / "output" / "compare_dist.md"))
    a = ap.parse_args()
    lexes = [load_konomeno(Path(a.kono))]
    for e in a.extra:
        name, _, p = e.partition("=")
        lexes.append(load_wordlist_ipa(Path(p), name))
    lexes += [load_northeuralex(l) for l in a.langs]
    out = Path(a.out)
    dists = write_report(lexes, out)
    plot(lexes, dists, out.parent, out.stem)
    print("wrote", out)


if __name__ == "__main__":
    main()
