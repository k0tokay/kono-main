"""書き換え規則 ``A -> B / C _ D`` を語に適用する.

規則は ``dsl.parse_rule`` の :class:`Rule`．照合は :meth:`Word.segment_tier`
（語境界・音節境界・位置素性つき）の上で行うので，文脈に ``#`` や
``[initial=false]``，``[role=coda]`` を書ける．置換 B は綴り字で与える．

1 規則は左から右へ 1 パス（重なりなし）で適用する．規則列は順に適用し，
各規則の後で語を再音節化する．
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .dsl import BoundarySymbol, Rule, parse_pattern, parse_rule
from .inventory import Inventory, inventory as _default_inv
from .word import Word


@dataclass(frozen=True)
class RuleSet:
    """名前つき規則の列．``map`` 形式（複数の literal 置換を同一文脈で）も展開して持つ."""

    rules: tuple[tuple[str, Rule], ...]

    @classmethod
    def from_toml(cls, path, inv: Inventory | None = None) -> "RuleSet":
        from .inventory import tomllib
        data = tomllib.loads(open(path, encoding="utf-8").read())
        inv = inv or _default_inv()
        out = []
        for r in data.get("rules", []):
            if r.get("enabled", True) is False:
                continue
            name = r["name"]
            if "rule" in r:
                out.append((name, parse_rule(r["rule"], name, inv)))
            elif "map" in r:
                ctx = r.get("context", "")
                for src, dst in r["map"].items():
                    text = f"{src} -> {dst or '∅'}" + (f" / {ctx}" if ctx else "")
                    out.append((name, parse_rule(text, name, inv)))
            else:
                raise ValueError(f"規則 {name!r} に rule も map もない")
        return cls(tuple(out))


def _left_ok(rule: Rule, tier, i: int) -> bool:
    if rule.left is None:
        return True
    def _only_syl_boundaries(a: int, b: int) -> bool:
        return all(isinstance(t, BoundarySymbol) and t.kind == "syllable" for t in tier[a:b])

    for j in range(i, -1, -1):
        if any(e <= i and _only_syl_boundaries(e, i) for e in rule.left.root.match(tier, j)):
            return True
    return False


def _right_ok(rule: Rule, tier, e: int) -> bool:
    if rule.right is None:
        return True
    return any(True for _ in rule.right.root.match(tier, e))


def apply_rule(word: Word, rule: Rule) -> tuple[str, int]:
    """1 語に 1 規則を適用し，(新しい綴り, 適用回数) を返す."""
    tier = word.segment_tier()
    n = len(tier)
    repl: dict[int, tuple[int, str]] = {}  # start -> (end, replacement)
    i = 0
    hits = 0
    while i < n:
        sym = tier[i]
        if isinstance(sym, BoundarySymbol):
            i += 1
            continue
        e = rule.target.match_at(tier, i)
        if e is not None and e > i and _left_ok(rule, tier, i) and _right_ok(rule, tier, e):
            repl[i] = (e, rule.replacement)
            hits += 1
            i = e
        else:
            i += 1
    if not hits:
        return word.spell, 0
    out = []
    i = 0
    while i < n:
        if i in repl:
            e, s = repl[i]
            out.append(s)
            i = e
            continue
        sym = tier[i]
        if not isinstance(sym, BoundarySymbol):
            out.append(sym.spell)
        i += 1
    return "".join(out), hits


@dataclass
class Derivation:
    source: str
    result: str
    steps: list[tuple[str, str]] = field(default_factory=list)  # (rule name, spelling after)

    @property
    def changed(self) -> bool:
        return self.source != self.result


def derive(spell: str, rules: RuleSet, inv: Inventory | None = None) -> Derivation:
    """規則列を順に適用する．各規則の後で再音節化する."""
    inv = inv or _default_inv()
    cur = spell
    d = Derivation(spell, spell)
    for name, rule in rules.rules:
        w = Word(cur, inv=inv)
        new, k = apply_rule(w, rule)
        if k and new != cur:
            d.steps.append((name, new))
            cur = new
    d.result = cur
    return d


__all__ = ["RuleSet", "apply_rule", "derive", "Derivation", "parse_rule", "parse_pattern"]
