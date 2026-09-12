"""形態音韻 — 母音結合 ``+`` と子音結合 ``⊕``.

``phonology.tex`` 「活用」節の定義を実装したもの．旧 ``word.py`` の
``plus`` / ``dotplus`` の再実装で、``Seq`` 上の純粋関数になっている．

定義（tex より）:

    Φ(x,y) = xy            (x,y) が核の制約を満たすとき
    μ(x,y) = i             x,y がどちらも円唇でない
           = y             otherwise

    ε + ε = a
    ε + y = y
    x + ε = x
    x + y = (Φ ⋎ Φᵀ ⋎ μ)(x, y)
    x + **y** = x j y₁
    **x**y + z = **x** + (y + z)
    **x** + **y** = x₁ j **y**
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .inventory import Inventory, Phoneme
from .seq import Seq

if TYPE_CHECKING:  # pragma: no cover
    pass


# ---------------------------------------------------------------------------
# 補助
# ---------------------------------------------------------------------------


def _split_tail_vowels(s: Seq) -> tuple[Seq, Seq]:
    """末尾の母音列を切り出す -> (残り, 母音列)."""
    i = len(s)
    while i > 0 and s[i - 1].is_vowel:
        i -= 1
    return s[:i], s[i:]


def _split_head_vowels(s: Seq) -> tuple[Seq, Seq]:
    """先頭の母音列を切り出す -> (母音列, 残り)."""
    i = 0
    while i < len(s) and s[i].is_vowel:
        i += 1
    return s[:i], s[i:]


def _split_tail_consonants(s: Seq) -> tuple[Seq, Seq]:
    i = len(s)
    while i > 0 and s[i - 1].is_consonant:
        i -= 1
    return s[:i], s[i:]


def _split_head_consonants(s: Seq) -> tuple[Seq, Seq]:
    i = 0
    while i < len(s) and s[i].is_consonant:
        i += 1
    return s[:i], s[i:]


def apply_spelling_rules(text: str, inv: Inventory) -> str:
    """口蓋化などの綴り字レベル書き換えを適用する."""
    for _name, mapping in inv.spelling_rules:
        changed = True
        while changed:
            changed = False
            for src, dst in mapping.items():
                if src in text:
                    text = text.replace(src, dst)
                    changed = True
    return text


# ---------------------------------------------------------------------------
# 母音結合
# ---------------------------------------------------------------------------


def _mu(a: Phoneme, b: Phoneme, inv: Inventory) -> Phoneme:
    """どちらも非円唇なら i、そうでなければ y."""
    rounded = bool(a.get("round")) or bool(b.get("round"))
    return inv["y"] if rounded else inv["i"]


def _join_two_vowels(a: Phoneme, b: Phoneme, inv: Inventory) -> Seq:
    pairs = inv.legal_nucleus_pairs
    if (a.spell, b.spell) in pairs:
        return Seq.of([a, b], inv)
    if (b.spell, a.spell) in pairs:
        return Seq.of([b, a], inv)
    return Seq.of([_mu(a, b, inv)], inv)


def _vjoin_vowels(x: Seq, y: Seq, inv: Inventory) -> Seq:
    """母音列同士の結合（tex の再帰的定義）."""
    if len(x) == 0 and len(y) == 0:
        return Seq.of("a", inv)
    if len(x) == 0:
        return y
    if len(y) == 0:
        return x
    if len(x) == 1 and len(y) == 1:
        return _join_two_vowels(x[0], y[0], inv)
    if len(x) == 1:  # x + **y** = x j y_1
        return Seq.of([x[0], inv["j"], y[0]], inv)
    if len(y) == 1:  # **x**y + z = **x** + (y + z)
        return _vjoin_vowels(x[:-1], _vjoin_vowels(x[-1:], y, inv), inv)
    return Seq.of([x[0], inv["j"]], inv) + y  # **x** + **y** = x_1 j **y**


def vowel_join(a: Seq, b: Seq) -> Seq:
    """語（音素列）同士の母音結合．tex の ``+``."""
    inv = a.inv
    if not a:
        return b
    if not b:
        return a
    head, tail_v = _split_tail_vowels(a)
    head_v, rest = _split_head_vowels(b)
    joined = _vjoin_vowels(tail_v, head_v, inv)
    text = head.spell + joined.spell + rest.spell
    return Seq.of(apply_spelling_rules(text, inv), inv)


# ---------------------------------------------------------------------------
# 子音結合
# ---------------------------------------------------------------------------


def _nu(p: Phoneme, inv: Inventory) -> Phoneme:
    """破擦音 -> 対応する摩擦音（ts -> s, tc -> c）."""
    if p.manner != "affricate":
        return p
    return inv["s"] if p.spell == "ts" else inv["c"]


def _cjoin_consonants(x: Seq, y: Seq, inv: Inventory) -> Seq:
    if len(x) == 0 and len(y) == 0:
        return Seq.of("n", inv)
    if len(x) == 0:
        return y
    if len(y) == 0:
        return x
    if len(x) == 1 and len(y) == 1:
        return Seq.of([_nu(x[0], inv), _nu(y[0], inv)], inv)
    if len(x) == 1:  # x ⊕ **y** = x a **y**
        return Seq.of([x[0], inv["a"]], inv) + y
    return _cjoin_consonants(x[:-1], _cjoin_consonants(x[-1:], y, inv), inv)


def consonant_join(a: Seq, b: Seq) -> Seq:
    """語同士の子音結合．tex の ``⊕``."""
    inv = a.inv
    if not a:
        return b
    if not b:
        return a
    head, tail_c = _split_tail_consonants(a)
    head_c, rest = _split_head_consonants(b)
    joined = _cjoin_consonants(tail_c, head_c, inv)
    text = head.spell + joined.spell + rest.spell
    return Seq.of(apply_spelling_rules(text, inv), inv)
