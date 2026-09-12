"""確率論・情報理論的な統計収集.

**設計の要点は tier の抽象化**である．「何を記号列とみなすか」だけを
差し替えれば、音素・自然類・音節構造・重さ・オンセット形といった
どのレベルでも同じ統計（遷移行列・エントロピー・相互情報量・PMI）が
取れる．

    >>> tiers = Tiers(inv)
    >>> ng = NgramModel.build(corpus, tiers.phoneme, n=2)
    >>> ng.transition_matrix()      # pandas DataFrame
    >>> ng.mutual_information()
    >>> ng.pmi_matrix()
    >>> ng.gaps()                   # 期待値が高いのに出現ゼロのセル
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Iterable, Sequence

import numpy as np
import pandas as pd

from .inventory import Inventory, inventory as default_inventory
from .prosody import RIME, get_scale

if TYPE_CHECKING:  # pragma: no cover
    from .word import Word

BOS, EOS = "⟨", "⟩"

TierFn = Callable[["Word"], list[str]]


# ---------------------------------------------------------------------------
# tier
# ---------------------------------------------------------------------------


@dataclass
class Tiers:
    """語を記号列に射影する関数の集まり."""

    inv: Inventory = field(default_factory=default_inventory)

    # -- セグメントレベル ------------------------------------------------
    def phoneme(self, w: "Word") -> list[str]:
        return [p.spell for p in w.seq]

    def ipa(self, w: "Word") -> list[str]:
        return [p.ipa for p in w.seq]

    def natural_class(self, w: "Word") -> list[str]:
        return list(w.seq.classes)

    def cv(self, w: "Word") -> list[str]:
        return list(w.seq.cv_skeleton)

    def feature(self, name: str) -> TierFn:
        def f(w: "Word") -> list[str]:
            return [str(p.features.get(name)) for p in w.seq]

        f.__name__ = f"feature[{name}]"
        return f

    def manner(self, w: "Word") -> list[str]:
        return [p.manner or "-" for p in w.seq]

    def place(self, w: "Word") -> list[str]:
        return [p.place or "-" for p in w.seq]

    def sonority(self, w: "Word") -> list[str]:
        return [str(int(p.sonority)) for p in w.seq]

    # -- 音節レベル ------------------------------------------------------
    def syllable(self, w: "Word") -> list[str]:
        return [s.spell for s in w.syllables]

    def syllable_shape(self, w: "Word") -> list[str]:
        return [s.shape for s in w.syllables]

    def syllable_class_shape(self, w: "Word") -> list[str]:
        return [s.class_shape for s in w.syllables]

    def onset_shape(self, w: "Word") -> list[str]:
        return ["".join(self.inv.class_of(p) for p in s.onset) or "∅" for s in w.syllables]

    def coda_shape(self, w: "Word") -> list[str]:
        return ["".join(self.inv.class_of(p) for p in s.coda) or "∅" for s in w.syllables]

    def weight(self, scale="rime") -> TierFn:
        sc = get_scale(scale, self.inv)

        def f(w: "Word") -> list[str]:
            return [sc.weight_class(s) for s in w.syllables]

        f.__name__ = f"weight[{sc.name}]"
        return f

    def mora(self, scale="rime") -> TierFn:
        sc = get_scale(scale, self.inv)

        def f(w: "Word") -> list[str]:
            return [str(sc.mora(s)) for s in w.syllables]

        f.__name__ = f"mora[{sc.name}]"
        return f

    def accent(self, w: "Word") -> list[str]:
        return list(str(w.accent)) if w.accent else []

    # -- 組み合わせ ------------------------------------------------------
    @staticmethod
    def zip_tiers(*fns: TierFn, sep: str = "/") -> TierFn:
        """複数 tier を対にした記号列（例 重さ×アクセント）."""

        def f(w: "Word") -> list[str]:
            cols = [fn(w) for fn in fns]
            if not cols or min(len(c) for c in cols) != max(len(c) for c in cols):
                return []
            return [sep.join(t) for t in zip(*cols)]

        f.__name__ = "zip(" + ",".join(getattr(x, "__name__", "?") for x in fns) + ")"
        return f


# ---------------------------------------------------------------------------
# n-gram
# ---------------------------------------------------------------------------


@dataclass
class NgramModel:
    n: int
    alpha: float
    vocab: list[str]
    counts: Counter
    context_counts: Counter
    n_sequences: int
    tier_name: str = ""

    # ------------------------------------------------------------------
    @classmethod
    def build(
        cls,
        words: Iterable["Word"],
        tier: TierFn,
        n: int = 2,
        alpha: float = 0.1,
        boundaries: bool = True,
    ) -> "NgramModel":
        counts: Counter = Counter()
        ctx: Counter = Counter()
        vocab: set[str] = set()
        n_seq = 0
        for w in words:
            syms = tier(w)
            if not syms:
                continue
            n_seq += 1
            seq = ([BOS] * (n - 1) + syms + [EOS]) if boundaries else list(syms)
            vocab.update(syms)
            for i in range(len(seq) - n + 1):
                g = tuple(seq[i : i + n])
                counts[g] += 1
                ctx[g[:-1]] += 1
        if boundaries:
            vocab.add(EOS)
        return cls(
            n=n,
            alpha=alpha,
            vocab=sorted(vocab),
            counts=counts,
            context_counts=ctx,
            n_sequences=n_seq,
            tier_name=getattr(tier, "__name__", str(tier)),
        )

    # -- 確率 -----------------------------------------------------------
    def prob(self, gram: Sequence[str]) -> float:
        g = tuple(gram)
        V = len(self.vocab)
        return (self.counts[g] + self.alpha) / (self.context_counts[g[:-1]] + self.alpha * V)

    def logprob_seq(self, syms: Sequence[str]) -> float:
        seq = [BOS] * (self.n - 1) + list(syms) + [EOS]
        return sum(
            math.log2(self.prob(seq[i : i + self.n])) for i in range(len(seq) - self.n + 1)
        )

    def score_word(self, w: "Word", tier: TierFn, normalize: bool = True) -> float:
        syms = tier(w)
        lp = self.logprob_seq(syms)
        return lp / max(1, len(syms) + 1) if normalize else lp

    # -- 行列 -----------------------------------------------------------
    def _contexts(self) -> list[tuple[str, ...]]:
        return sorted({g[:-1] for g in self.counts})

    def count_matrix(self) -> pd.DataFrame:
        rows = self._contexts()
        idx = ["".join(r) if self.n > 2 else (r[0] if r else "") for r in rows]
        M = np.zeros((len(rows), len(self.vocab)))
        col = {s: j for j, s in enumerate(self.vocab)}
        for i, r in enumerate(rows):
            for s, j in col.items():
                M[i, j] = self.counts[r + (s,)]
        return pd.DataFrame(M, index=idx, columns=self.vocab)

    def transition_matrix(self, smoothed: bool = True) -> pd.DataFrame:
        C = self.count_matrix()
        if smoothed:
            P = (C.values + self.alpha) / (C.values.sum(axis=1, keepdims=True) + self.alpha * len(self.vocab))
        else:
            tot = C.values.sum(axis=1, keepdims=True)
            P = np.divide(C.values, tot, out=np.zeros_like(C.values), where=tot > 0)
        return pd.DataFrame(P, index=C.index, columns=C.columns)

    # -- 情報量 ---------------------------------------------------------
    def _joint(self) -> tuple[np.ndarray, list, list]:
        C = self.count_matrix()
        J = C.values / C.values.sum()
        return J, list(C.index), list(C.columns)

    def entropy(self) -> float:
        """H(X_t)（周辺エントロピー，bit）."""
        J, _, _ = self._joint()
        p = J.sum(axis=0)
        p = p[p > 0]
        return float(-(p * np.log2(p)).sum())

    def conditional_entropy(self) -> float:
        """H(X_t | X_{t-1})."""
        J, _, _ = self._joint()
        px = J.sum(axis=1, keepdims=True)
        with np.errstate(divide="ignore", invalid="ignore"):
            cond = np.where(J > 0, J * np.log2(np.where(px > 0, J / px, 1)), 0.0)
        return float(-cond.sum())

    def mutual_information(self) -> float:
        """I(X_{t-1}; X_t)."""
        return self.entropy() - self.conditional_entropy()

    def redundancy(self) -> float:
        h = self.entropy()
        return 0.0 if h == 0 else self.mutual_information() / h

    def pmi_matrix(self, min_count: int = 1) -> pd.DataFrame:
        J, idx, cols = self._joint()
        px = J.sum(axis=1, keepdims=True)
        py = J.sum(axis=0, keepdims=True)
        with np.errstate(divide="ignore", invalid="ignore"):
            P = np.log2(J / (px * py))
        C = self.count_matrix().values
        P = np.where(C >= min_count, P, np.nan)
        return pd.DataFrame(P, index=idx, columns=cols)

    def gaps(self, min_expected: float = 1.0) -> pd.DataFrame:
        """出現ゼロだが期待値が高いセル（＝制約候補）."""
        J, idx, cols = self._joint()
        C = self.count_matrix().values
        N = C.sum()
        E = J.sum(axis=1, keepdims=True) * J.sum(axis=0, keepdims=True) * N
        rows = []
        for i, a in enumerate(idx):
            for j, b in enumerate(cols):
                if C[i, j] == 0 and E[i, j] >= min_expected:
                    rows.append({"x": a, "y": b, "observed": 0, "expected": round(float(E[i, j]), 2)})
        return pd.DataFrame(rows).sort_values("expected", ascending=False, ignore_index=True)

    def summary(self) -> dict:
        return {
            "tier": self.tier_name,
            "n": self.n,
            "n_sequences": self.n_sequences,
            "vocab": len(self.vocab),
            "n_grams_seen": len(self.counts),
            "H(X)": round(self.entropy(), 4),
            "H(X|prev)": round(self.conditional_entropy(), 4),
            "I": round(self.mutual_information(), 4),
            "redundancy": round(self.redundancy(), 4),
        }


# ---------------------------------------------------------------------------
# 記述統計
# ---------------------------------------------------------------------------


def tier_distribution(words: Iterable["Word"], tier: TierFn) -> pd.DataFrame:
    c: Counter = Counter()
    for w in words:
        c.update(tier(w))
    tot = sum(c.values()) or 1
    return pd.DataFrame(
        [{"symbol": k, "count": v, "freq": v / tot} for k, v in c.most_common()]
    )


def positional_distribution(words: Iterable["Word"], tier: TierFn, from_end: bool = False) -> pd.DataFrame:
    """位置ごとの記号分布（末尾からの位置でも取れる）."""
    rows = []
    for w in words:
        syms = tier(w)
        n = len(syms)
        for i, s in enumerate(syms):
            rows.append({"pos": (n - i) if from_end else (i + 1), "symbol": s})
    if not rows:
        return pd.DataFrame(columns=["pos", "symbol", "count", "freq"])
    df = pd.DataFrame(rows).value_counts(["pos", "symbol"]).reset_index(name="count")
    df["freq"] = df.groupby("pos")["count"].transform(lambda s: s / s.sum())
    return df.sort_values(["pos", "count"], ascending=[True, False], ignore_index=True)


def cooccurrence(
    words: Iterable["Word"], tier_a: TierFn, tier_b: TierFn, min_count: int = 0
) -> pd.DataFrame:
    """2つの tier の同位置共起表（例: 音節重さ × アクセント）."""
    c: Counter = Counter()
    for w in words:
        a, b = tier_a(w), tier_b(w)
        if len(a) != len(b):
            continue
        c.update(zip(a, b))
    if not c:
        return pd.DataFrame()
    rows = sorted({k[0] for k in c})
    cols = sorted({k[1] for k in c})
    M = pd.DataFrame(0, index=rows, columns=cols)
    for (x, y), v in c.items():
        if v >= min_count:
            M.loc[x, y] = v
    return M


def chi2_independence(table: pd.DataFrame) -> dict:
    """共起表の独立性検定（Cramér's V つき）."""
    from scipy.stats import chi2_contingency

    obs = table.values.astype(float)
    if obs.size == 0 or obs.sum() == 0 or min(obs.shape) < 2:
        return {"chi2": float("nan"), "p": float("nan"), "cramers_v": float("nan")}
    chi2, p, dof, exp = chi2_contingency(obs)
    n = obs.sum()
    v = math.sqrt(chi2 / (n * (min(obs.shape) - 1)))
    return {"chi2": chi2, "p": p, "dof": dof, "cramers_v": v, "expected": exp}
