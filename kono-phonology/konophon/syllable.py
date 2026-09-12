"""音節と音節化.

:class:`Syllable` は ``(onset, nucleus, coda)`` の三つ組．
:class:`Syllabifier` は音素列を音節列に分割する．既定は
**最大オンセット原則 (MOP)**（``phonology.tex`` 「音節化」）だが、
明示的な境界指定でこれを上書きできる（``naz|loft`` のような
形態的・意味的境界のケース）．

実装方針: 貪欲法ではなく**全解の列挙 + スコアリング**にしてある．
MOP を「オンセット総和の最大化」というスコアで表現しておくと、
別の原則（ソノリティ優先、コーダ最大化など）に差し替えるのが
スコア関数の入れ替えだけで済む．語は短いので列挙のコストは無視できる．
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property, lru_cache
from typing import Any, Callable, Iterable, Mapping, Sequence

from .inventory import Inventory, Phoneme, inventory as default_inventory
from .prosody import RIME, WeightScale
from .seq import Seq

BOUNDARY_CHARS = ".|"


@dataclass(frozen=True, slots=True)
class Syllable:
    """音節 σ = ω ν κ."""

    onset: Seq
    nucleus: Seq
    coda: Seq
    index: int = -1  # 語内での位置（0 始まり）．未設定は -1
    n_syllables: int = -1
    accent: str = ""

    # -- 基本 -----------------------------------------------------------
    @property
    def rime(self) -> Seq:
        return self.nucleus + self.coda

    @property
    def segments(self) -> Seq:
        return self.onset + self.nucleus + self.coda

    @property
    def spell(self) -> str:
        return self.segments.spell

    def __str__(self) -> str:
        return self.spell

    def __repr__(self) -> str:  # pragma: no cover
        return f"σ({self.onset.spell}|{self.nucleus.spell}|{self.coda.spell})"

    def __len__(self) -> int:
        return len(self.segments)

    @property
    def is_open(self) -> bool:
        return len(self.coda) == 0

    @property
    def shape(self) -> str:
        """``CCVVC`` のような骨格."""
        return "C" * len(self.onset) + "V" * len(self.nucleus) + "C" * len(self.coda)

    @property
    def class_shape(self) -> str:
        """``TL-V-N`` のような自然類による骨格."""
        inv = self.nucleus.inv
        f = lambda s: "".join(inv.class_of(p) for p in s)
        return f"{f(self.onset)}-{f(self.nucleus)}-{f(self.coda)}"

    # -- 韻律 -----------------------------------------------------------
    def mora(self, scale: WeightScale = RIME) -> int:
        return scale.mora(self)

    def licensing_mora(self, scale: WeightScale = RIME) -> int:
        return scale.licensing_mora(self)

    def weight(self, scale: WeightScale = RIME) -> str:
        return scale.weight_class(self)

    # -- パターン照合用の素性 --------------------------------------------
    @property
    def features(self) -> Mapping[str, Any]:
        d: dict[str, Any] = {
            "unit": "syllable",
            "onset_size": len(self.onset),
            "nucleus_size": len(self.nucleus),
            "coda_size": len(self.coda),
            "open": self.is_open,
            "shape": self.shape,
            "mora": RIME.mora(self),
            "weight": RIME.weight_class(self),
            "accent": self.accent or None,
            "index": self.index,
        }
        if self.n_syllables > 0 and self.index >= 0:
            d["initial"] = self.index == 0
            d["final"] = self.index == self.n_syllables - 1
            d["penult"] = self.index == self.n_syllables - 2
            d["from_end"] = self.n_syllables - self.index
        return d

    # 便宜: Symbol プロトコル互換のため spell 属性も見せる
    @property
    def spell_attr(self) -> str:  # pragma: no cover
        return self.spell

    def with_(self, **kw) -> "Syllable":
        from dataclasses import replace

        return replace(self, **kw)


# ---------------------------------------------------------------------------
# 音節化
# ---------------------------------------------------------------------------


class SyllabifyError(ValueError):
    pass


ScoreFn = Callable[[Sequence[tuple[int, int, int]]], tuple]


def mop_score(parts: Sequence[tuple[int, int, int]]) -> tuple:
    """最大オンセット原則: オンセット総和を最大化、次に音節数を最小化."""
    return (sum(o for o, _, _ in parts), -len(parts), tuple(o for o, _, _ in parts))


def max_coda_score(parts: Sequence[tuple[int, int, int]]) -> tuple:
    """比較用: コーダ最大化."""
    return (sum(c for _, _, c in parts), -len(parts))


@dataclass
class Syllabifier:
    """音素列 -> 音節列."""

    inv: Inventory
    score: ScoreFn = mop_score

    def __init__(
        self,
        inv: Inventory | None = None,
        score: ScoreFn = mop_score,
        *,
        fallback_relaxed: bool = True,
    ):
        self.inv = inv or default_inventory()
        self.score = score
        self.fallback_relaxed = fallback_relaxed
        self.relax = False
        cfg = self.inv.syllable_cfg
        self.onset_max = cfg.get("onset_max", 2)
        self.nucleus_max = cfg.get("nucleus_max", 2)
        self.coda_max = cfg.get("coda_max", 2)

    # -- 合法性 ---------------------------------------------------------
    def legal_onset(self, s: Seq) -> bool:
        if len(s) > self.onset_max or any(p.is_vowel for p in s):
            return False
        if len(s) == 2 and not self.relax:
            return (s[0].spell, s[1].spell) in self.inv.legal_onset_pairs
        return True

    def legal_nucleus(self, s: Seq) -> bool:
        if not 1 <= len(s) <= self.nucleus_max or any(not p.is_vowel for p in s):
            return False
        if len(s) == 2 and not self.relax:
            return (s[0].spell, s[1].spell) in self.inv.legal_nucleus_pairs
        return True

    def legal_coda(self, s: Seq) -> bool:
        if len(s) > self.coda_max or any(p.is_vowel for p in s):
            return False
        if len(s) == 2 and not self.relax:
            return (s[0].spell, s[1].spell) in self.inv.legal_coda_pairs
        return True

    def illegal_parts(self, syls: Sequence[Syllable]) -> list[str]:
        """結合表に載っていない ω / ν / κ を列挙する（緩和音節化の診断用）."""
        out = []
        for i, s in enumerate(syls):
            for label, part, table in (
                ("ω", s.onset, self.inv.legal_onset_pairs),
                ("ν", s.nucleus, self.inv.legal_nucleus_pairs),
                ("κ", s.coda, self.inv.legal_coda_pairs),
            ):
                if len(part) == 2 and (part[0].spell, part[1].spell) not in table:
                    out.append(f"σ{i + 1} {label}={part.spell} は結合表に無い")
        return out

    # -- 本体 -----------------------------------------------------------
    def all_parses(
        self, seq: Seq, forced: frozenset[int] = frozenset()
    ) -> list[list[Syllable]]:
        """合法な音節化をすべて列挙する．``forced`` は強制境界の位置集合."""
        n = len(seq)
        results: list[list[tuple[int, int, int]]] = []

        def rec(i: int, acc: list[tuple[int, int, int]]):
            if i == n:
                results.append(list(acc))
                return
            for o in range(0, self.onset_max + 1):
                if i + o > n:
                    break
                # オンセットの内側に強制境界が来てはならない
                if any(b in forced for b in range(i + 1, i + o + 1)):
                    break
                on = seq[i : i + o]
                if not self.legal_onset(on):
                    continue
                for nu_len in range(1, self.nucleus_max + 1):
                    j = i + o + nu_len
                    if j > n:
                        break
                    if any(b in forced for b in range(i + o + 1, j)):
                        break
                    nu = seq[i + o : j]
                    if not self.legal_nucleus(nu):
                        continue
                    for c in range(0, self.coda_max + 1):
                        k = j + c
                        if k > n:
                            break
                        if any(b in forced for b in range(j + 1, k)):
                            break
                        co = seq[j:k]
                        if not self.legal_coda(co):
                            continue
                        if k < n and k in forced or k == n or k not in forced:
                            # 強制境界は音節境界と一致していなければならない
                            pass
                        rec(k, acc + [(o, nu_len, c)])

        rec(0, [])

        out: list[list[Syllable]] = []
        for parts in results:
            # 強制境界がすべて音節境界になっているか
            bounds = set()
            pos = 0
            for o, nu, c in parts:
                pos += o + nu + c
                bounds.add(pos)
            if not forced <= bounds:
                continue
            out.append(self._build(seq, parts))
        return out

    def _build(self, seq: Seq, parts: Sequence[tuple[int, int, int]]) -> list[Syllable]:
        syls = []
        pos = 0
        for idx, (o, nu, c) in enumerate(parts):
            syls.append(
                Syllable(
                    onset=seq[pos : pos + o],
                    nucleus=seq[pos + o : pos + o + nu],
                    coda=seq[pos + o + nu : pos + o + nu + c],
                    index=idx,
                    n_syllables=len(parts),
                )
            )
            pos += o + nu + c
        return syls

    def _best(self, seq: Seq, forced: frozenset[int]) -> list[Syllable] | None:
        parses = self.all_parses(seq, forced)
        if not parses:
            return None
        keyed = [
            (self.score([(len(s.onset), len(s.nucleus), len(s.coda)) for s in p]), p)
            for p in parses
        ]
        keyed.sort(key=lambda t: t[0], reverse=True)
        return keyed[0][1]

    def parse(self, seq: Seq, forced: Iterable[int] = ()) -> tuple[list[Syllable], list[str]]:
        """(音節列, 診断メッセージ) を返す.

        結合表を厳密に守る解が無い場合、``fallback_relaxed`` なら表を無視した
        解を返し、どこが表に無いかを診断メッセージに入れる．語彙と宣言済み
        制約表の齟齬を握り潰さずに可視化するための設計．
        """
        forced = frozenset(forced)
        self.relax = False
        best = self._best(seq, forced)
        if best is not None:
            return best, []
        if not self.fallback_relaxed:
            raise SyllabifyError(f"音節化できない: {seq.spell!r}")
        self.relax = True
        try:
            best = self._best(seq, forced)
        finally:
            self.relax = False
        if best is None:
            raise SyllabifyError(f"音節化できない（緩和しても不可）: {seq.spell!r}")
        return best, self.illegal_parts(best)

    def __call__(self, seq: Seq, forced: Iterable[int] = ()) -> list[Syllable]:
        return self.parse(seq, forced)[0]


# ---------------------------------------------------------------------------
# 境界つき文字列のパース
# ---------------------------------------------------------------------------


def split_boundaries(text: str, inv: Inventory | None = None) -> tuple[Seq, frozenset[int]]:
    """``naz.loft`` / ``naz|loft`` を (音素列, 強制境界位置) に分解する."""
    inv = inv or default_inventory()
    clean = []
    forced: set[int] = set()
    count = 0
    for ch in text:
        if ch in BOUNDARY_CHARS:
            forced.add(count)
            continue
        clean.append(ch)
        # 音素境界と文字境界がずれるので、後でトークン数に直す
        count = len("".join(clean))
    # 文字数ベースの位置を音素 index に変換
    spell = "".join(clean)
    phs = inv.tokenize(spell)
    char_to_idx: dict[int, int] = {}
    acc = 0
    for i, p in enumerate(phs):
        char_to_idx[acc] = i
        acc += len(p.spell)
    char_to_idx[acc] = len(phs)
    idxs = set()
    for f in forced:
        if f not in char_to_idx:
            raise SyllabifyError(f"境界 '.' が音素の途中にある: {text!r}")
        idxs.add(char_to_idx[f])
    idxs.discard(0)
    idxs.discard(len(phs))
    return Seq(tuple(phs), inv), frozenset(idxs)
