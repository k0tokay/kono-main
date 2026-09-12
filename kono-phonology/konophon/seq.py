"""音素列 :class:`Seq` — 不変列としての基本演算.

``Seq`` は音素の不変列である．結合 ``+``、スライス、繰り返し ``*``、
包含 ``in`` といった Python 標準の列演算に加えて、CV グループ化・
素性射影・パターン照合を提供する．

形態音韻的な結合（tex の ``+`` と ``⊕``）は列演算ではないので
:mod:`konophon.morphology` に置き、``Seq`` 側では ``vplus`` / ``cplus``
という名前で参照できるようにしている（``+`` は素の連結を意味する）．
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING, Iterable, Iterator, Sequence, overload

from .dsl import WORD_BOUNDARY, Pattern, Symbol, parse_pattern
from .inventory import Inventory, Phoneme, inventory as default_inventory

if TYPE_CHECKING:  # pragma: no cover
    from .word import Word


@dataclass(frozen=True, slots=True)
class Seq(Sequence[Phoneme]):
    """音素の不変列."""

    items: tuple[Phoneme, ...]
    inv: Inventory

    # -- 構築 -----------------------------------------------------------
    @classmethod
    def of(
        cls,
        source: "str | Seq | Iterable[Phoneme | str]",
        inv: Inventory | None = None,
    ) -> "Seq":
        inv = inv or (source.inv if isinstance(source, Seq) else default_inventory())
        if isinstance(source, Seq):
            return source if source.inv is inv else cls(source.items, inv)
        if isinstance(source, str):
            return cls(tuple(inv.tokenize(source)), inv)
        items = []
        for x in source:
            items.append(inv[x] if isinstance(x, str) else x)
        return cls(tuple(items), inv)

    # -- Sequence プロトコル ---------------------------------------------
    def __len__(self) -> int:
        return len(self.items)

    @overload
    def __getitem__(self, i: int) -> Phoneme: ...
    @overload
    def __getitem__(self, i: slice) -> "Seq": ...

    def __getitem__(self, i):
        if isinstance(i, slice):
            return Seq(self.items[i], self.inv)
        return self.items[i]

    def __iter__(self) -> Iterator[Phoneme]:
        return iter(self.items)

    def __contains__(self, x: object) -> bool:
        if isinstance(x, str):
            return any(p.spell == x for p in self.items)
        return x in self.items

    # -- 演算 -----------------------------------------------------------
    def __add__(self, other: "Seq | str | Iterable[Phoneme]") -> "Seq":
        o = other if isinstance(other, Seq) else Seq.of(other, self.inv)
        return Seq(self.items + o.items, self.inv)

    def __radd__(self, other) -> "Seq":
        return Seq.of(other, self.inv) + self

    def __mul__(self, n: int) -> "Seq":
        return Seq(self.items * n, self.inv)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Seq):
            return self.items == other.items
        if isinstance(other, str):
            return self.spell == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.items)

    def __bool__(self) -> bool:
        return bool(self.items)

    def __str__(self) -> str:
        return self.spell

    def __repr__(self) -> str:
        return f"Seq({self.spell!r})"

    # -- 表記 -----------------------------------------------------------
    @property
    def spell(self) -> str:
        return "".join(p.spell for p in self.items)

    @property
    def ipa(self) -> str:
        from .phonetics import to_ipa

        return to_ipa(self)

    # -- 射影 -----------------------------------------------------------
    def project(self, feature: str) -> tuple:
        """各音素の素性値を並べたタプル（tier 生成の基礎）."""
        return tuple(p.features.get(feature) for p in self.items)

    @property
    def cv_skeleton(self) -> str:
        """``CVCCV`` のような骨格文字列."""
        return "".join("V" if p.is_vowel else "C" for p in self.items)

    @property
    def classes(self) -> tuple[str, ...]:
        """各音素の自然類略号 (S/Q/T/N/L/J/V)."""
        return tuple(self.inv.class_of(p) for p in self.items)

    def cv_groups(self) -> list["Seq"]:
        """母音列と子音列に交互に分割する."""
        out: list[Seq] = []
        cur: list[Phoneme] = []
        prev: bool | None = None
        for p in self.items:
            v = p.is_vowel
            if prev is not None and v != prev:
                out.append(Seq(tuple(cur), self.inv))
                cur = []
            cur.append(p)
            prev = v
        if cur:
            out.append(Seq(tuple(cur), self.inv))
        return out

    # -- 照合 -----------------------------------------------------------
    def tier(self, *, boundaries: bool = True) -> list[Symbol]:
        """パターン照合用のシンボル列（語境界つき）."""
        if not boundaries:
            return list(self.items)
        return [WORD_BOUNDARY, *self.items, WORD_BOUNDARY]

    def _pat(self, pattern: "Pattern | str") -> Pattern:
        return pattern if isinstance(pattern, Pattern) else parse_pattern(pattern, self.inv)

    def matches(self, pattern: "Pattern | str") -> bool:
        return self._pat(pattern).search(self.tier())

    def count(self, pattern: "Pattern | str") -> int:
        return self._pat(pattern).count(self.tier())

    def find_all(self, pattern: "Pattern | str") -> list[tuple[int, int]]:
        return self._pat(pattern).find_all(self.tier())

    # -- 形態音韻的結合（morphology への委譲） ----------------------------
    def vplus(self, other: "Seq | str") -> "Seq":
        """母音結合（tex の ``+``）."""
        from .morphology import vowel_join

        return vowel_join(self, Seq.of(other, self.inv))

    def cplus(self, other: "Seq | str") -> "Seq":
        """子音結合（tex の ``⊕``）."""
        from .morphology import consonant_join

        return consonant_join(self, Seq.of(other, self.inv))

    # -- 音節化 ---------------------------------------------------------
    def syllabify(self, **kw) -> "Word":
        from .word import Word

        return Word(self, **kw)
