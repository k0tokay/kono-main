"""音素 bigram モデルによる単語尤度の評価。

v5 辞書（正典）の見出し語から BOS/EOS 付き bigram 頻度をとり、
単語の「らしさ」を長さ正規化した対数尤度で評価する。
ルールベース化の参考として、高頻度 bigram・未出現 bigram（ギャップ）も出力する。

用法:
  python3 bigram_likelihood.py             # 辞書全体のスコア分布と bigram 表
  python3 bigram_likelihood.py melon kakin # 任意の語をスコアリング
"""

import math
import sys
from collections import Counter

from phonemes import PHONEMES, tokenize, load_v5_entries

BOS, EOS = "<", ">"


class BigramModel:
    def __init__(self, words, alpha=0.1):
        """words: 綴り文字列のリスト。alpha: 加算スムージング。"""
        self.alpha = alpha
        self.uni = Counter()
        self.bi = Counter()
        self.words = []
        for w in words:
            ph = tokenize(w)
            if ph is None:
                continue
            self.words.append((w, ph))
            seq = [BOS] + ph + [EOS]
            self.uni.update(seq[:-1])
            self.bi.update(zip(seq, seq[1:]))
        self.vocab = PHONEMES + [EOS]

    def logp(self, x, y):
        """log2 P(y|x)（加算スムージング）"""
        return math.log2((self.bi[(x, y)] + self.alpha) /
                         (self.uni[x] + self.alpha * len(self.vocab)))

    def score(self, word):
        """長さ正規化した平均 log2 尤度。トークン化不能なら None。"""
        ph = tokenize(word)
        if ph is None:
            return None
        seq = [BOS] + ph + [EOS]
        return sum(self.logp(x, y) for x, y in zip(seq, seq[1:])) / (len(seq) - 1)

    def worst_bigrams(self, word):
        ph = tokenize(word)
        if ph is None:
            return []
        seq = [BOS] + ph + [EOS]
        return sorted(((self.logp(x, y), x, y) for x, y in zip(seq, seq[1:])))


def main():
    model = BigramModel(load_v5_entries())
    print(f"学習語数: {len(model.words)}, bigram 種類数: {len(model.bi)}")

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        for w in args:
            s = model.score(w)
            if s is None:
                print(f"{w}: トークン化不能")
                continue
            worst = model.worst_bigrams(w)[:3]
            detail = ", ".join(f"{x}{y}:{lp:.1f}" for lp, x, y in worst)
            print(f"{w}: {s:.2f}  (弱い遷移: {detail})")
        return

    # --- 辞書全体の分布 ---
    scored = sorted(((model.score(w), w) for w, _ in model.words), reverse=True)
    scores = [s for s, _ in scored]
    n = len(scores)
    mean = sum(scores) / n
    var = sum((s - mean) ** 2 for s in scores) / n
    print(f"\n平均 log2 尤度/遷移: {mean:.3f}  (sd={math.sqrt(var):.3f})")
    qs = [scores[int(n * q)] for q in (0.05, 0.25, 0.5, 0.75, 0.95)]
    print("分位点 (95/75/50/25/5%):", "  ".join(f"{q:.2f}" for q in qs))

    print("\n最も『らしい』20語:")
    for s, w in scored[:20]:
        print(f"  {s:6.2f}  {w}")
    print("\n最も『らしくない』20語（借用感・例外候補）:")
    for s, w in scored[-20:]:
        print(f"  {s:6.2f}  {w}")

    # --- ルールベース化の参考 ---
    print("\n高頻度 bigram 上位30（骨格候補）:")
    total = sum(model.bi.values())
    for (x, y), c in model.bi.most_common(30):
        print(f"  {x:>2s} {y:<2s}  {c:4d}  ({c/total:.3f})")

    attested_x = {x for x, _ in model.bi}
    gaps = [(x, y) for x in attested_x if x != EOS
            for y in PHONEMES + [EOS]
            if model.uni[x] >= 20 and model.bi[(x, y)] == 0]
    print(f"\nギャップ（頻出音素からの未出現遷移, 前件≥20回）: {len(gaps)} 個")
    by_x = {}
    for x, y in gaps:
        by_x.setdefault(x, []).append(y)
    for x in sorted(by_x, key=lambda x: -model.uni[x]):
        print(f"  {x} ({model.uni[x]}回) → ✗ {' '.join(by_x[x])}")


if __name__ == "__main__":
    main()
