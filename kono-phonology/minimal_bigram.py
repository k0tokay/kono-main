"""ミニマルセット音素の bigram 遷移と、平衡化モデルの割り当ての突き合わせ。

- CV / VC の bigram 頻度と条件付き確率 P(y|x) のヒートマップ
- V-C-V トリグラムで、子音 c を挟んだ母音の α/β 成分の一致率を計測
  → coining.tex の透過性 θ の割り当て（t,k=遮断 / n=βのみ / l=αのみ / m,f=両透過）と比較

用法: python3 minimal_bigram.py
"""

from collections import Counter

import numpy as np
import matplotlib
import matplotlib.pyplot as plt

matplotlib.rcParams["font.family"] = "Hiragino Sans"

from phonemes import tokenize, load_v5_entries
from minimal_set import VOWELS, CONSONANTS  # 色割り当てと θ

MIN_V = list(VOWELS)       # o a i e
MIN_C = list(CONSONANTS)   # t k n l m f
OUT = "output"


def collect():
    cv, vc = Counter(), Counter()
    vcv = Counter()
    for w in load_v5_entries():
        ph = tokenize(w)
        if ph is None:
            continue
        for x, y in zip(ph, ph[1:]):
            if x in MIN_C and y in MIN_V:
                cv[(x, y)] += 1
            if x in MIN_V and y in MIN_C:
                vc[(x, y)] += 1
        for a, c, b in zip(ph, ph[1:], ph[2:]):
            if a in MIN_V and c in MIN_C and b in MIN_V:
                vcv[(a, c, b)] += 1
    return cv, vc, vcv


def heatmap(ax, counts, rows, cols, title, normalize_rows):
    M = np.array([[counts[(r, c)] for c in cols] for r in rows], dtype=float)
    disp = M / M.sum(axis=1, keepdims=True) if normalize_rows else M
    im = ax.imshow(disp, cmap="viridis")
    ax.set_xticks(range(len(cols)), cols)
    ax.set_yticks(range(len(rows)), rows)
    for i in range(len(rows)):
        for j in range(len(cols)):
            v = disp[i, j]
            txt = f"{v:.2f}" if normalize_rows else f"{int(M[i,j])}"
            ax.text(j, i, txt, ha="center", va="center",
                    color="white" if v < disp.max() * 0.6 else "black", fontsize=9)
    ax.set_title(title)
    return im


def theta_check(vcv):
    """子音 c を挟んだ母音対 (v1,v2) の成分一致率と θ を比較する。"""
    print("V-C-V: 子音を挟んだ母音成分の一致率 vs θ")
    print(f"{'c':>3s} {'n':>5s} {'α一致':>7s} {'β一致':>7s}   θ=(α,β)")
    # ベースライン: 語彙全体の母音分布から独立に引いたときの一致率
    base = Counter()
    for (a, c, b), n in vcv.items():
        base[a] += n
        base[b] += n
    tot = sum(base.values())
    pa = {v: base[v] / tot for v in MIN_V}
    base_alpha = sum(pa[u] * pa[v] for u in MIN_V for v in MIN_V
                     if VOWELS[u][0] == VOWELS[v][0])
    base_beta = sum(pa[u] * pa[v] for u in MIN_V for v in MIN_V
                    if VOWELS[u][1] == VOWELS[v][1])
    for c in MIN_C:
        pairs = [((a, b), n) for (a, cc, b), n in vcv.items() if cc == c]
        n = sum(x for _, x in pairs)
        if n == 0:
            continue
        agree_a = sum(x for (a, b), x in pairs if VOWELS[a][0] == VOWELS[b][0]) / n
        agree_b = sum(x for (a, b), x in pairs if VOWELS[a][1] == VOWELS[b][1]) / n
        th = CONSONANTS[c]
        print(f"{c:>3s} {n:5d} {agree_a:7.2f} {agree_b:7.2f}   "
              f"({'透過' if th[0] else '遮断'},{'透過' if th[1] else '遮断'})")
    print(f"{'偶然':>3s} {'':5s} {base_alpha:7.2f} {base_beta:7.2f}   （独立ベースライン）")
    print("透過なら一致率がベースラインより高いはず（調和が実在すれば）")


# ---- 素性ベースの拡張（main-detail 印象表 tab:phoneme-impression） ----
# 大きさ(3値)・重さ(2値: 円唇性)・質感(2値)
V_FEATURES = {
    #      大きさ 重さ 質感 a b g
    "a": ("大", "軽", "粗", 1, 1, 1),
    "o": ("大", "重", "滑", 1, 0, 0),
    "e": ("中", "軽", "粗", 1, -1, 0),
    "i": ("小", "軽", "滑", 0, 0, 0),
    "y": ("小", "重", "滑", 1/2, 1/2, 1),
    "u": ("小", "軽", "滑", 1/2, 1/2, -1),
    "v": ("小", "重", "粗", 1/2, 1/2, -1),
}
FEATURE_NAMES = ["大きさ", "重さ", "質感", "a", "b", "g"]
FEATURE_NUM = len(FEATURE_NAMES)


def feature_harmony(min_n=10):
    """全母音・全子音の V-C-V で、印象素性ごとの一致率を測る。"""
    from phonemes import CONSONANTS as ALL_C
    vcv = Counter()
    for w in load_v5_entries():
        ph = tokenize(w)
        if ph is None:
            continue
        for a, c, b in zip(ph, ph[1:], ph[2:]):
            if a in V_FEATURES and c in ALL_C and b in V_FEATURES:
                vcv[(a, c, b)] += 1

    # ベースライン（母音周辺分布から独立仮定）
    marg = Counter()
    for (a, c, b), n in vcv.items():
        marg[a] += n
        marg[b] += n
    tot = sum(marg.values())
    p = {v: marg[v] / tot for v in V_FEATURES}
    base = [sum(p[u] * p[v] for u in V_FEATURES for v in V_FEATURES
                if V_FEATURES[u][k] == V_FEATURES[v][k]) for k in range(FEATURE_NUM)]

    print(f"\n全音素 V-C-V: 印象素性の一致率（n≥{min_n} の子音のみ）")
    print(f"{'c':>3s} {'n':>5s} " + " ".join(f"{f:>6s}" for f in FEATURE_NAMES))
    rows = []
    for c in ALL_C:
        pairs = [((a, b), n) for (a, cc, b), n in vcv.items() if cc == c]
        n = sum(x for _, x in pairs)
        if n < min_n:
            continue
        ag = [sum(x for (a, b), x in pairs if V_FEATURES[a][k] == V_FEATURES[b][k]) / n
              for k in range(FEATURE_NUM)]
        rows.append((n, c, ag))
    for n, c, ag in sorted(rows, reverse=True):
        marks = "".join("+" if a > base[k] + 0.1 else "-" if a < base[k] - 0.1 else " "
                        for k, a in enumerate(ag))
        print(f"{c:>3s} {n:5d} " + " ".join(f"{a:6.2f}" for a in ag) + f"   [{marks}]")
    print(f"{'偶然':>3s} {'':5s} " + " ".join(f"{b:6.2f}" for b in base) +
          "   （+/-: ベースライン±0.1 超）")


def main():
    cv, vc, vcv = collect()

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    heatmap(axes[0, 0], cv, MIN_C, MIN_V, "CV: 頻度", False)
    heatmap(axes[0, 1], cv, MIN_C, MIN_V, "CV: P(V|C)", True)
    heatmap(axes[1, 0], vc, MIN_V, MIN_C, "VC: 頻度", False)
    heatmap(axes[1, 1], vc, MIN_V, MIN_C, "VC: P(C|V)", True)
    fig.suptitle("ミニマルセット bigram（v5 語彙サブツリー）", fontsize=13)
    plt.tight_layout()
    out = f"{OUT}/minimal_bigram_heatmap.png"
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"→ {out}\n")

    theta_check(vcv)
    feature_harmony()


if __name__ == "__main__":
    main()
