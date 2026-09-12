"""制約と尤度 — 「この規則候補はどれくらい本物か」を数値にする.

# 考え方

音韻規則の候補を **markedness 制約** ``*P`` として書く．
語 :math:`w` の調和度を

.. math:: H(w) = \\sum_i w_i \\, C_i(w)

とし、確率モデルを **baseline 分布 q の指数傾斜** として定義する:

.. math:: P(w) = \\frac{q(w)\\,e^{-H(w)}}{Z}, \\quad Z = \\mathbb{E}_q[e^{-H}]

これは Hayes & Wilson (2008) の maxent 音素配列モデルと同じ形である．
``q`` を「音素の unigram をランダムに並べたもの」に取ると、
:math:`H` は「単なる音素頻度では説明できない配列上の偏り」だけを担う．

# 使い方

    >>> g = Grammar.from_inventory(inv)              # toml の既知制約を読む
    >>> g.harmony(word)
    >>> ev = evaluate(Constraint("*[C][C][C]"), corpus, baseline)
    >>> ev.oe_ratio, ev.p_value, ev.delta_loglik

``evaluate`` は次を返す:

O
    語彙中の実観測違反数
E
    baseline 下での期待違反数
O/E
    1 より十分小さければ「避けられている」＝制約として本物らしい
p
    二項検定（違反を含む語の割合について）
ΔlogLik
    その制約を文法に追加したときの対数尤度の改善量
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Iterable, Sequence

import numpy as np

from .dsl import Pattern, parse_pattern
from .inventory import Inventory, inventory as default_inventory

if TYPE_CHECKING:  # pragma: no cover
    from .word import Word

HARD = float("inf")


# ---------------------------------------------------------------------------
# 制約
# ---------------------------------------------------------------------------


@dataclass
class Constraint:
    """markedness 制約 ``*P``."""

    pattern: str
    name: str = ""
    weight: float = 1.0
    tier: str = "segment"
    doc: str = ""
    status: str = ""
    _compiled: Pattern | None = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if not self.name:
            self.name = self.pattern

    def compile(self, inv: Inventory | None = None) -> Pattern:
        if self._compiled is None:
            self._compiled = parse_pattern(self.pattern, inv or default_inventory())
        return self._compiled

    @property
    def is_hard(self) -> bool:
        return math.isinf(self.weight)

    def violations(self, word: "Word") -> int:
        return self.compile(word.inv).count(word.tier(self.tier))

    def violated_by(self, word: "Word") -> bool:
        return self.violations(word) > 0

    def __str__(self) -> str:
        w = "∞" if self.is_hard else f"{self.weight:.3g}"
        return f"{self.name} [{w}]"


def _coerce_weight(x) -> float:
    if isinstance(x, str):
        return HARD if x.strip().lower() in ("inf", "∞", "hard") else float(x)
    return float(x)


# ---------------------------------------------------------------------------
# 文法
# ---------------------------------------------------------------------------


@dataclass
class Grammar:
    constraints: list[Constraint] = field(default_factory=list)
    inv: Inventory = field(default_factory=default_inventory)

    @classmethod
    def from_inventory(cls, inv: Inventory | None = None) -> "Grammar":
        """``phonology.toml`` の ``[[constraints]]`` を読み込む."""
        inv = inv or default_inventory()
        cs = [
            Constraint(
                pattern=d["pattern"],
                name=d.get("name", d["pattern"]),
                weight=_coerce_weight(d.get("weight", 1.0)),
                tier=d.get("tier", "segment"),
                doc=d.get("doc", ""),
                status=d.get("status", ""),
            )
            for d in inv.declared_constraints
        ]
        return cls(cs, inv)

    def __len__(self) -> int:
        return len(self.constraints)

    def __iter__(self):
        return iter(self.constraints)

    def add(self, c: Constraint) -> "Grammar":
        return Grammar(self.constraints + [c], self.inv)

    # -- 評価 -----------------------------------------------------------
    def violation_vector(self, word: "Word") -> np.ndarray:
        return np.array([c.violations(word) for c in self.constraints], dtype=float)

    def violation_matrix(self, words: Sequence["Word"]) -> np.ndarray:
        return np.array([self.violation_vector(w) for w in words], dtype=float)

    def harmony(self, word: "Word") -> float:
        """H(w)．hard 制約に違反したら inf."""
        h = 0.0
        for c in self.constraints:
            v = c.violations(word)
            if v:
                if c.is_hard:
                    return HARD
                h += c.weight * v
        return h

    def is_legal(self, word: "Word") -> bool:
        return not math.isinf(self.harmony(word))

    def explain(self, word: "Word") -> list[tuple[str, int, float]]:
        """(制約名, 違反数, 寄与) の一覧．"""
        out = []
        for c in self.constraints:
            v = c.violations(word)
            if v:
                out.append((c.name, v, HARD if c.is_hard else c.weight * v))
        return sorted(out, key=lambda t: -t[2])

    # -- 学習 -----------------------------------------------------------
    def fit(
        self,
        words: Sequence["Word"],
        samples: Sequence["Word"],
        *,
        l2: float = 1.0,
        nonneg: bool = True,
        max_iter: int = 400,
    ) -> "FitResult":
        """MaxEnt 重み推定（soft 制約のみ更新，hard は固定）."""
        from scipy.optimize import minimize

        soft = [i for i, c in enumerate(self.constraints) if not c.is_hard]
        if not soft:
            return FitResult(self, np.array([]), 0.0, 0)
        Cd = self.violation_matrix(words)[:, soft]
        Cs = self.violation_matrix(samples)[:, soft]
        obs = Cd.mean(axis=0)

        def nll_grad(w):
            hd = Cd @ w
            hs = Cs @ w
            m = -hs.max()
            ex = np.exp(-hs + m)
            Z = ex.mean()
            logZ = np.log(Z) - m
            nll = hd.mean() + logZ + l2 * 0.5 * float(w @ w)
            exp_model = (Cs * ex[:, None]).sum(axis=0) / ex.sum()
            grad = obs - exp_model + l2 * w
            return nll, grad

        w0 = np.array([self.constraints[i].weight for i in soft], dtype=float)
        w0 = np.where(np.isfinite(w0), w0, 1.0)
        res = minimize(
            nll_grad,
            w0,
            jac=True,
            method="L-BFGS-B",
            bounds=[(0.0, None)] * len(soft) if nonneg else None,
            options={"maxiter": max_iter},
        )
        new = list(self.constraints)
        for k, i in enumerate(soft):
            new[i] = Constraint(
                pattern=new[i].pattern,
                name=new[i].name,
                weight=float(res.x[k]),
                tier=new[i].tier,
                doc=new[i].doc,
                status=new[i].status,
            )
        g = Grammar(new, self.inv)
        return FitResult(g, res.x, float(res.fun), int(res.nit))

    def loglik(self, words: Sequence["Word"], samples: Sequence["Word"]) -> float:
        """baseline 傾斜モデルの平均対数尤度（baseline 項を除く相対値）."""
        w = np.array([0.0 if c.is_hard else c.weight for c in self.constraints])
        Cd = self.violation_matrix(words)
        Cs = self.violation_matrix(samples)
        hard = np.array([c.is_hard for c in self.constraints])
        if hard.any():
            ok = (Cs[:, hard] == 0).all(axis=1)
            Cs = Cs[ok]
            if len(Cs) == 0:
                return float("-inf")
        hd = Cd @ w
        hs = Cs @ w
        m = -hs.max()
        logZ = np.log(np.exp(-hs + m).mean()) - m
        return float(-(hd.mean()) - logZ)


@dataclass
class FitResult:
    grammar: Grammar
    weights: np.ndarray
    nll: float
    n_iter: int

    def table(self):
        import pandas as pd

        return pd.DataFrame(
            [
                {"name": c.name, "pattern": c.pattern, "weight": c.weight, "doc": c.doc}
                for c in self.grammar.constraints
            ]
        ).sort_values("weight", ascending=False, ignore_index=True)


# ---------------------------------------------------------------------------
# baseline 分布
# ---------------------------------------------------------------------------


@dataclass
class Baseline:
    """語彙の統計だけを保ったランダム語生成器（帰無仮説）.

    ``mode``
        ``"unigram"``     音素 unigram 頻度で iid 生成
        ``"positional"``  語頭・語中・語末で別々の unigram を使う
        ``"cv"``          CV 骨格の分布を保ったうえで各位置を C/V 内で iid 生成
    """

    inv: Inventory
    mode: str = "cv"
    lengths: np.ndarray = field(default_factory=lambda: np.array([]))
    require_syllabifiable: bool = False
    _tables: dict = field(default_factory=dict, repr=False)

    @classmethod
    def fit(
        cls,
        words: Sequence["Word"],
        mode: str = "cv",
        inv: Inventory | None = None,
        require_syllabifiable: bool = False,
    ) -> "Baseline":
        inv = inv or (words[0].inv if words else default_inventory())
        b = cls(inv=inv, mode=mode, require_syllabifiable=require_syllabifiable)
        b.lengths = np.array([len(w.seq) for w in words])
        from collections import Counter

        uni, ini, fin, med = Counter(), Counter(), Counter(), Counter()
        cons, vows = Counter(), Counter()
        skeletons = Counter()
        for w in words:
            ph = list(w.seq)
            skeletons[w.seq.cv_skeleton] += 1
            for i, p in enumerate(ph):
                uni[p.spell] += 1
                (cons if p.is_consonant else vows)[p.spell] += 1
                if i == 0:
                    ini[p.spell] += 1
                elif i == len(ph) - 1:
                    fin[p.spell] += 1
                else:
                    med[p.spell] += 1
        b._tables = {
            "uni": _dist(uni, inv),
            "ini": _dist(ini, inv),
            "fin": _dist(fin, inv),
            "med": _dist(med, inv),
            "C": _dist(cons, inv),
            "V": _dist(vows, inv),
            "skeleton": _dist(skeletons, inv, symbols=list(skeletons)),
        }
        return b

    # ------------------------------------------------------------------
    def sample(self, n: int, rng: np.random.Generator | None = None) -> list["Word"]:
        from .word import Word

        rng = rng or np.random.default_rng(0)
        out: list[Word] = []
        tries = 0
        max_tries = n * 200
        while len(out) < n and tries < max_tries:
            tries += 1
            spell = self._sample_spell(rng)
            w = Word.try_make(spell, inv=self.inv)
            if w is None:
                if self.require_syllabifiable:
                    continue
                # 音節化できなくても素性列としては評価したいので Seq のまま扱う
                w = _RawWord(spell, self.inv)
            out.append(w)
        return out

    def _sample_spell(self, rng) -> str:
        if self.mode == "cv":
            syms, probs = self._tables["skeleton"]
            sk = syms[rng.choice(len(syms), p=probs)]
            parts = []
            for ch in sk:
                s, p = self._tables[ch]
                parts.append(s[rng.choice(len(s), p=p)])
            return "".join(parts)
        L = int(rng.choice(self.lengths))
        parts = []
        for i in range(L):
            key = "ini" if i == 0 else ("fin" if i == L - 1 else "med")
            s, p = self._tables[key if self.mode == "positional" else "uni"]
            parts.append(s[rng.choice(len(s), p=p)])
        return "".join(parts)


def _dist(counter, inv, symbols=None):
    syms = symbols if symbols is not None else list(counter)
    tot = sum(counter[s] for s in syms)
    if tot == 0:
        return syms, np.ones(len(syms)) / max(1, len(syms))
    return syms, np.array([counter[s] / tot for s in syms])


class _RawWord:
    """音節化できない生成語のための最小限のダミー（segment tier のみ）."""

    def __init__(self, spell: str, inv: Inventory):
        from .seq import Seq

        self.inv = inv
        self.seq = Seq.of(spell, inv)
        self.syllables = []
        self.accent = None
        self.gloss = ""
        self.meta = {}

    @property
    def spell(self):
        return self.seq.spell

    def tier(self, name="segment"):
        if name == "syllable":
            return []
        return self.seq.tier()

    def __repr__(self):  # pragma: no cover
        return f"<raw {self.spell}>"


# ---------------------------------------------------------------------------
# 制約候補の評価
# ---------------------------------------------------------------------------


@dataclass
class Evaluation:
    constraint: Constraint
    observed: int          # 語彙中の違反総数
    expected: float        # baseline 下の期待違反総数（語彙サイズに換算）
    n_words_obs: int       # 違反を含む語の数
    n_words_exp: float     # baseline 下でその割合になる語数の期待値
    p_value: float
    delta_loglik: float
    n_lexicon: int
    n_samples: int

    @property
    def oe_ratio(self) -> float:
        return self.observed / self.expected if self.expected > 0 else float("nan")

    @property
    def log_odds(self) -> float:
        a, b = self.n_words_obs + 0.5, self.n_lexicon - self.n_words_obs + 0.5
        c = self.n_words_exp + 0.5
        d = self.n_lexicon - self.n_words_exp + 0.5
        return math.log((a / b) / (c / d))

    @property
    def verdict(self) -> str:
        if self.observed == 0 and self.expected >= 3:
            return "絶対制約の候補（語彙中ゼロ・期待値十分）"
        if self.p_value < 0.01 and self.oe_ratio < 0.5:
            return "有意に回避されている"
        if self.p_value < 0.05 and self.oe_ratio < 0.8:
            return "弱く回避されている"
        if self.p_value < 0.01 and self.oe_ratio > 1.5:
            return "有意に選好されている（制約の向きが逆かも）"
        return "帰無仮説と区別できない"

    def as_row(self) -> dict:
        return {
            "name": self.constraint.name,
            "pattern": self.constraint.pattern,
            "O": self.observed,
            "E": round(self.expected, 2),
            "O/E": round(self.oe_ratio, 3) if self.expected else None,
            "words_O": self.n_words_obs,
            "words_E": round(self.n_words_exp, 2),
            "log_odds": round(self.log_odds, 3),
            "p": self.p_value,
            "dLL": round(self.delta_loglik, 4),
            "verdict": self.verdict,
        }


def evaluate(
    constraint: Constraint | str,
    words: Sequence["Word"],
    baseline_samples: Sequence,
    *,
    grammar: Grammar | None = None,
) -> Evaluation:
    """制約候補を語彙と baseline サンプルの比較で評価する."""
    from scipy.stats import binomtest

    if isinstance(constraint, str):
        constraint = Constraint(constraint)

    inv = words[0].inv if words else default_inventory()
    pat = constraint.compile(inv)
    tier = constraint.tier

    obs_counts = [pat.count(w.tier(tier)) for w in words]
    smp_counts = [pat.count(w.tier(tier)) for w in baseline_samples]
    N, M = len(words), max(1, len(baseline_samples))

    O = int(sum(obs_counts))
    E = float(sum(smp_counts)) / M * N
    wo = sum(1 for c in obs_counts if c)
    we_rate = sum(1 for c in smp_counts if c) / M
    we = we_rate * N

    if 0.0 < we_rate < 1.0:
        p = binomtest(wo, N, we_rate).pvalue
    else:
        p = 1.0 if (we_rate == 0 and wo == 0) or (we_rate == 1 and wo == N) else 0.0

    base = grammar or Grammar([], inv)
    ll0 = base.loglik(words, baseline_samples)
    g1 = base.add(Constraint(constraint.pattern, constraint.name, 1.0, tier))
    fit = g1.fit(words, baseline_samples, l2=0.01)
    ll1 = fit.grammar.loglik(words, baseline_samples)

    return Evaluation(
        constraint=constraint,
        observed=O,
        expected=E,
        n_words_obs=wo,
        n_words_exp=we,
        p_value=float(p),
        delta_loglik=float(ll1 - ll0),
        n_lexicon=N,
        n_samples=M,
    )


def evaluate_many(
    candidates: Iterable[Constraint | str],
    words: Sequence["Word"],
    baseline_samples: Sequence,
    *,
    grammar: Grammar | None = None,
):
    """複数候補を評価して DataFrame にする."""
    import pandas as pd

    rows = [evaluate(c, words, baseline_samples, grammar=grammar).as_row() for c in candidates]
    return pd.DataFrame(rows).sort_values("dLL", ascending=False, ignore_index=True)
