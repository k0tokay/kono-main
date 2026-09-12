"""
音韻類型分析モジュール
音素分布・音素連接（bigram）・エントロピー・PMI を計算する汎用ライブラリ。
任意の言語に適用可能。

gogaku.tex「類型の分析」セクションの記述に基づく:
  - bigram P(x_t | x_{t-1}) with <BOS>/<EOS>
  - 条件付きエントロピー H(X_t | X_{t-1})
  - 隣接音素間相互情報量 I(X_{t-1}; X_t)
  - PMI(i, j) = log[p(i,j) / (p(i)*p(j))]
"""

from collections import Counter
from dataclasses import dataclass, field

import numpy as np

BOS = "<BOS>"
EOS = "<EOS>"


@dataclass
class PhonemeStats:
    name: str
    words: list[list[str]]
    unigram: Counter = field(default_factory=Counter)
    bigram: Counter = field(default_factory=Counter)
    initial: Counter = field(default_factory=Counter)
    final: Counter = field(default_factory=Counter)
    n_tokens: int = 0
    n_types: int = 0
    phoneme_inventory: list[str] = field(default_factory=list)

    def __post_init__(self):
        self._compute()

    def _compute(self):
        for ph_list in self.words:
            if not ph_list:
                continue
            self.unigram.update(ph_list)
            self.initial[ph_list[0]] += 1
            self.final[ph_list[-1]] += 1
            seq = [BOS] + ph_list + [EOS]
            self.bigram.update(zip(seq, seq[1:]))
        self.n_tokens = sum(self.unigram.values())
        self.n_types = len(self.unigram)
        self.phoneme_inventory = [ph for ph, _ in self.unigram.most_common()]

    def ranked_freq(self):
        ranked = sorted(self.unigram.values(), reverse=True)
        freqs = np.array(ranked) / self.n_tokens
        ranks = np.arange(1, len(freqs) + 1)
        return ranks, freqs

    def bigram_matrix(self):
        symbols = [BOS] + self.phoneme_inventory + [EOS]
        idx = {s: i for i, s in enumerate(symbols)}
        n = len(symbols)
        mat = np.zeros((n, n))
        for (a, b), c in self.bigram.items():
            mat[idx[a], idx[b]] = c
        return symbols, mat

    def transition_prob(self):
        symbols, mat = self.bigram_matrix()
        row_sums = mat.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1
        return symbols, mat / row_sums

    def conditional_entropy(self):
        """H(X_t | X_{t-1})"""
        symbols, P = self.transition_prob()
        _, counts = self.bigram_matrix()
        row_totals = counts.sum(axis=1)
        total = counts.sum()
        H = 0.0
        for i in range(len(symbols)):
            if row_totals[i] == 0:
                continue
            p_prev = row_totals[i] / total
            for j in range(len(symbols)):
                if P[i, j] > 0:
                    H -= p_prev * P[i, j] * np.log2(P[i, j])
        return H

    def mutual_information(self):
        """I(X_{t-1}; X_t) = H(X_t) - H(X_t | X_{t-1})"""
        all_next = Counter()
        for (_, b), c in self.bigram.items():
            all_next[b] += c
        total = sum(all_next.values())
        H_Xt = -sum((c / total) * np.log2(c / total) for c in all_next.values() if c > 0)
        H_cond = self.conditional_entropy()
        return H_Xt - H_cond

    def pmi_matrix(self, min_count=2):
        """PMI(i, j) = log2[p(i,j) / (p(i)*p(j))]"""
        symbols, counts = self.bigram_matrix()
        total = counts.sum()
        row_totals = counts.sum(axis=1)
        col_totals = counts.sum(axis=0)
        n = len(symbols)
        pmi = np.full((n, n), np.nan)
        for i in range(n):
            for j in range(n):
                if counts[i, j] >= min_count and row_totals[i] > 0 and col_totals[j] > 0:
                    p_ij = counts[i, j] / total
                    p_i = row_totals[i] / total
                    p_j = col_totals[j] / total
                    pmi[i, j] = np.log2(p_ij / (p_i * p_j))
        return symbols, pmi

    def top_pmi_pairs(self, min_count=2, top_n=30):
        symbols, pmi = self.pmi_matrix(min_count=min_count)
        pairs = []
        for i in range(len(symbols)):
            for j in range(len(symbols)):
                if not np.isnan(pmi[i, j]):
                    _, counts = self.bigram_matrix()
                    pairs.append((symbols[i], symbols[j], pmi[i, j], int(counts[i, j])))
        pairs.sort(key=lambda x: -x[2])
        return pairs[:top_n]

    def bottom_pmi_pairs(self, min_count=2, top_n=30):
        symbols, pmi = self.pmi_matrix(min_count=min_count)
        pairs = []
        for i in range(len(symbols)):
            for j in range(len(symbols)):
                if not np.isnan(pmi[i, j]):
                    _, counts = self.bigram_matrix()
                    pairs.append((symbols[i], symbols[j], pmi[i, j], int(counts[i, j])))
        pairs.sort(key=lambda x: x[2])
        return pairs[:top_n]

    def unigram_entropy(self):
        """H(X) — 音素のユニグラムエントロピー"""
        total = self.n_tokens
        return -sum((c / total) * np.log2(c / total) for c in self.unigram.values() if c > 0)

    def summary_dict(self):
        return {
            "name": self.name,
            "n_words": len(self.words),
            "n_tokens": self.n_tokens,
            "n_phonemes": self.n_types,
            "H_unigram": self.unigram_entropy(),
            "H_cond": self.conditional_entropy(),
            "MI": self.mutual_information(),
            "H_max": np.log2(self.n_types) if self.n_types > 0 else 0,
        }
