"""素性列 DSL — 音韻パターン・制約・書き換え規則の記法.

# 記法

## セグメント指定
    [+cons]              二値素性
    [-son, +cons]        コンマ（または空白）区切りは AND
    [place=labial]       カテゴリ素性
    [sonor>=6]           スカラー素性（>= <= > < = != が使える）
    [C] [V] [S] [T] ...  自然類の略号（phonology.toml の [classes]）
    C V S Q T N L J      1文字の大文字は括弧なしでも自然類として読む
    []                   任意のセグメント（ワイルドカード）
    <ts>  または ts      綴り字リテラル（小文字の連なりは音素列に分解される）
    [!N]                 自然類の否定

## 構造
    #        語境界（語頭・語末）
    .        音節境界
    (A | B)  選択
    A?  A*  A+  A{2}  A{1,3}   量化子
    _        規則の焦点位置

## 制約
    *P       P が現れることを禁止する markedness 制約
             （例: ``*[C][C][C][C]`` = 子音4連続の禁止）

## 書き換え規則
    A -> B / C _ D     C と D に挟まれた A を B にする（/以下は省略可）
    A -> 0 / ...       削除（0 / ∅ どちらでも可）

# 評価の対象（tier）
パターンは「素性を持つシンボルの列」に対して照合される．
:mod:`konophon.word` の ``Word.segment_tier()`` は音素列に語境界・音節境界
シンボルを差し込んだものを返し，``Word.syllable_tier()`` は音節を
シンボルとする列を返す．同じ DSL がどちらにも適用できる．
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterator, Mapping, Protocol, Sequence

if TYPE_CHECKING:  # pragma: no cover
    from .inventory import Inventory, Phoneme

__all__ = [
    "Symbol",
    "BoundarySymbol",
    "WORD_BOUNDARY",
    "SYLLABLE_BOUNDARY",
    "SegmentSpec",
    "Pattern",
    "Rule",
    "parse_pattern",
    "parse_segment_spec",
    "parse_rule",
]


# ---------------------------------------------------------------------------
# 照合対象のシンボル
# ---------------------------------------------------------------------------


class Symbol(Protocol):
    """パターン照合の対象となるもの（音素・音節・境界）."""

    @property
    def features(self) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class BoundarySymbol:
    """語境界 ``#`` / 音節境界 ``.``."""

    kind: str  # "word" | "syllable"

    @property
    def features(self) -> Mapping[str, Any]:
        return {"boundary": self.kind}

    def __str__(self) -> str:
        return "#" if self.kind == "word" else "."


WORD_BOUNDARY = BoundarySymbol("word")
SYLLABLE_BOUNDARY = BoundarySymbol("syllable")


# ---------------------------------------------------------------------------
# セグメント指定（素性行列）
# ---------------------------------------------------------------------------

_OPS = {
    "=": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
}


@dataclass(frozen=True)
class FeatureTest:
    name: str
    op: str
    value: Any
    negated: bool = False

    def __call__(self, feats: Mapping[str, Any]) -> bool:
        got = feats.get(self.name, None)
        if self.op in (">=", "<=", ">", "<"):
            if not isinstance(got, (int, float)) or isinstance(got, bool):
                ok = False
            else:
                ok = _OPS[self.op](float(got), float(self.value))
        elif self.op == "=":
            ok = got == self.value if isinstance(self.value, bool) else str(got) == str(self.value)
        elif self.op == "!=":
            ok = got != self.value if isinstance(self.value, bool) else str(got) != str(self.value)
        else:  # pragma: no cover
            raise ValueError(self.op)
        return not ok if self.negated else ok

    def __str__(self) -> str:
        if self.op == "=" and self.value is True:
            return ("!" if self.negated else "") + "+" + self.name
        if self.op == "=" and self.value is False:
            return ("!" if self.negated else "") + "-" + self.name
        return f"{'!' if self.negated else ''}{self.name}{self.op}{self.value}"


@dataclass(frozen=True)
class SegmentSpec:
    """素性の連言．すべての ``tests`` を満たすシンボルにマッチする."""

    tests: tuple[FeatureTest, ...] = ()
    source: str = "[]"

    def matches(self, sym: Symbol) -> bool:
        if isinstance(sym, BoundarySymbol):
            return False
        feats = sym.features
        return all(t(feats) for t in self.tests)

    # 音素だけを対象にした版（Inventory.classes の構築で使う）
    def matches_phoneme(self, ph: "Phoneme") -> bool:
        return all(t(ph.features) for t in self.tests)

    def __str__(self) -> str:
        return self.source


ANY_SEGMENT = SegmentSpec((), "[]")


# ---------------------------------------------------------------------------
# パターン要素
# ---------------------------------------------------------------------------


class Node:
    """パターン木のノード．``match(seq, i)`` は終了位置の候補を yield する."""

    def match(self, seq: Sequence[Symbol], i: int) -> Iterator[int]:  # pragma: no cover
        raise NotImplementedError


def _skip_syllable_boundaries(seq: Sequence[Symbol], i: int) -> int:
    """音節境界シンボルを読み飛ばす.

    音節境界は「明示的に ``.`` と書いたときだけ」意味を持つ透明な記号として
    扱う．こうしないと ``*[C][C][C][C]``（子音4連続の禁止）が音節境界を
    またげず、``suis.kant`` のような語を取りこぼす．語境界 ``#`` は
    読み飛ばさない．
    """
    while i < len(seq) and isinstance(seq[i], BoundarySymbol) and seq[i].kind == "syllable":
        i += 1
    return i


@dataclass(frozen=True)
class SegNode(Node):
    spec: SegmentSpec

    def match(self, seq, i):
        j = _skip_syllable_boundaries(seq, i)
        if j < len(seq) and self.spec.matches(seq[j]):
            yield j + 1

    def __str__(self):
        return str(self.spec)


@dataclass(frozen=True)
class LiteralNode(Node):
    spell: str

    def match(self, seq, i):
        j = _skip_syllable_boundaries(seq, i)
        if j < len(seq):
            s = seq[j]
            if getattr(s, "spell", None) == self.spell:
                yield j + 1

    def __str__(self):
        return f"<{self.spell}>"


@dataclass(frozen=True)
class BoundaryNode(Node):
    kind: str

    def match(self, seq, i):
        if i < len(seq) and isinstance(seq[i], BoundarySymbol) and seq[i].kind == self.kind:
            yield i + 1

    def __str__(self):
        return "#" if self.kind == "word" else "."


@dataclass(frozen=True)
class FocusNode(Node):
    """規則の ``_``．照合上は幅0."""

    def match(self, seq, i):
        yield i

    def __str__(self):
        return "_"


@dataclass(frozen=True)
class SeqNode(Node):
    items: tuple[Node, ...]

    def match(self, seq, i):
        if not self.items:
            yield i
            return

        def rec(k: int, pos: int) -> Iterator[int]:
            if k == len(self.items):
                yield pos
                return
            for nxt in self.items[k].match(seq, pos):
                yield from rec(k + 1, nxt)

        yield from rec(0, i)

    def __str__(self):
        return "".join(str(x) for x in self.items)


@dataclass(frozen=True)
class AltNode(Node):
    options: tuple[Node, ...]

    def match(self, seq, i):
        seen = set()
        for o in self.options:
            for e in o.match(seq, i):
                if e not in seen:
                    seen.add(e)
                    yield e

    def __str__(self):
        return "(" + "|".join(str(o) for o in self.options) + ")"


@dataclass(frozen=True)
class RepeatNode(Node):
    item: Node
    lo: int
    hi: float  # math.inf 可

    def match(self, seq, i):
        # 貪欲に長い方から
        results: list[int] = []

        def rec(count: int, pos: int):
            if count >= self.lo:
                results.append(pos)
            if count >= self.hi:
                return
            for nxt in self.item.match(seq, pos):
                if nxt == pos:  # 幅0の無限ループ防止
                    continue
                rec(count + 1, nxt)

        rec(0, i)
        seen = set()
        for r in sorted(results, reverse=True):
            if r not in seen:
                seen.add(r)
                yield r

    def __str__(self):
        hi = "" if self.hi == float("inf") else int(self.hi)
        if (self.lo, self.hi) == (0, float("inf")):
            q = "*"
        elif (self.lo, self.hi) == (1, float("inf")):
            q = "+"
        elif (self.lo, self.hi) == (0, 1):
            q = "?"
        else:
            q = f"{{{self.lo},{hi}}}"
        return f"{self.item}{q}"


# ---------------------------------------------------------------------------
# パーサ
# ---------------------------------------------------------------------------


class ParseError(ValueError):
    pass


_FEAT_ITEM = re.compile(
    r"""\s*(?:
        (?P<neg>!)?
        (?:
            (?P<sign>[+-])(?P<signed>\w+)
          | (?P<name>\w+)\s*(?P<op>!=|>=|<=|=|>|<)\s*(?P<val>[\w.\-]+)
          | (?P<cls>\w+)
        )
    )\s*""",
    re.X,
)


class _Parser:
    def __init__(self, text: str, inv: "Inventory | None", resolve_classes: bool = True):
        self.s = text
        self.i = 0
        self.inv = inv
        self.resolve_classes = resolve_classes

    # -- 低レベル -------------------------------------------------------
    def eof(self) -> bool:
        return self.i >= len(self.s)

    def peek(self) -> str:
        return self.s[self.i] if self.i < len(self.s) else ""

    def error(self, msg: str):
        raise ParseError(f"{msg} (位置 {self.i} of {self.s!r})")

    def skip_ws(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    # -- 素性指定 -------------------------------------------------------
    def parse_bracket_spec(self) -> SegmentSpec:
        start = self.i
        assert self.peek() == "["
        self.i += 1
        depth = 1
        buf = []
        while not self.eof():
            ch = self.s[self.i]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    self.i += 1
                    break
            buf.append(ch)
            self.i += 1
        else:
            self.error("']' が閉じていない")
        body = "".join(buf).strip()
        src = self.s[start : self.i]
        return self._spec_from_body(body, src)

    def _spec_from_body(self, body: str, src: str) -> SegmentSpec:
        if not body:
            return SegmentSpec((), src)
        tests: list[FeatureTest] = []
        for raw in re.split(r"[,\s]+", body):
            if not raw:
                continue
            m = _FEAT_ITEM.fullmatch(raw)
            if not m:
                self.error(f"素性項を解釈できない: {raw!r}")
            neg = bool(m.group("neg"))
            if m.group("signed"):
                tests.append(FeatureTest(m.group("signed"), "=", m.group("sign") == "+", neg))
            elif m.group("name"):
                val: Any = m.group("val")
                if val in ("true", "false"):
                    val = val == "true"
                else:
                    try:
                        val = float(val) if "." in val else int(val)
                    except ValueError:
                        pass
                tests.append(FeatureTest(m.group("name"), m.group("op"), val, neg))
            else:
                tests.extend(self._class_tests(m.group("cls"), neg))
        return SegmentSpec(tuple(tests), src)

    def _class_tests(self, name: str, neg: bool, _depth: int = 0) -> list[FeatureTest]:
        if _depth > 8:
            self.error(f"自然類 {name!r} の定義が循環している")
        if self.inv is None or not self.resolve_classes:
            self.error(f"自然類 {name!r} を解決できない（Inventory 未指定）")
        expr = self.inv.class_defs.get(name)
        if expr is None:
            self.error(f"未知の自然類: {name!r}（[classes] に無い）")
        inner = _Parser(expr, self.inv, self.resolve_classes)
        inner.skip_ws()
        spec = inner.parse_bracket_spec()
        if not neg:
            return list(spec.tests)
        # 否定: 連言の否定は選言なので単一 SegmentSpec で表せない。
        # 実用上は単一素性の類のみ許す。
        if len(spec.tests) != 1:
            self.error(f"複合素性の自然類 {name!r} は否定できない（(A|B) を使う）")
        t = spec.tests[0]
        return [FeatureTest(t.name, t.op, t.value, not t.negated)]

    # -- 原子 -----------------------------------------------------------
    def parse_atom(self) -> Node | None:
        self.skip_ws()
        if self.eof():
            return None
        ch = self.peek()
        if ch == "[":
            return SegNode(self.parse_bracket_spec())
        if ch == "(":
            self.i += 1
            opts = [self.parse_seq(stop=")|")]
            while self.peek() == "|":
                self.i += 1
                opts.append(self.parse_seq(stop=")|"))
            if self.peek() != ")":
                self.error("')' が閉じていない")
            self.i += 1
            return AltNode(tuple(opts))
        if ch == "<":
            j = self.s.find(">", self.i)
            if j < 0:
                self.error("'>' が閉じていない")
            spell = self.s[self.i + 1 : j]
            self.i = j + 1
            return LiteralNode(spell)
        if ch == "#":
            self.i += 1
            return BoundaryNode("word")
        if ch == ".":
            self.i += 1
            return BoundaryNode("syllable")
        if ch == "_":
            self.i += 1
            return FocusNode()
        if ch == "σ":
            self.i += 1
            return SegNode(self._spec_from_body("unit=syllable", "σ"))
        if ch.isupper():
            self.i += 1
            return SegNode(self._spec_from_body(ch, ch))
        if ch.islower():
            m = re.match(r"[a-z]+", self.s[self.i :])
            run = m.group(0)
            self.i += len(run)
            if self.inv is None:
                self.error("リテラルの分解に Inventory が必要")
            phs = self.inv.tokenize(run)
            nodes = [LiteralNode(p.spell) for p in phs]
            return nodes[0] if len(nodes) == 1 else SeqNode(tuple(nodes))
        return None

    def parse_quantified(self) -> Node | None:
        atom = self.parse_atom()
        if atom is None:
            return None
        # 直前が複数音素のリテラル列なら、量化子は最後の要素にかける
        while True:
            ch = self.peek()
            if ch == "?":
                self.i += 1
                atom = self._wrap_last(atom, 0, 1)
            elif ch == "*":
                self.i += 1
                atom = self._wrap_last(atom, 0, float("inf"))
            elif ch == "+":
                self.i += 1
                atom = self._wrap_last(atom, 1, float("inf"))
            elif ch == "{":
                j = self.s.find("}", self.i)
                if j < 0:
                    self.error("'}' が閉じていない")
                body = self.s[self.i + 1 : j]
                self.i = j + 1
                if "," in body:
                    a, _, b = body.partition(",")
                    lo = int(a) if a.strip() else 0
                    hi = float(b) if b.strip() else float("inf")
                else:
                    lo = hi = int(body)
                atom = self._wrap_last(atom, lo, hi)
            else:
                return atom

    @staticmethod
    def _wrap_last(node: Node, lo: int, hi: float) -> Node:
        if isinstance(node, SeqNode) and node.items:
            return SeqNode(node.items[:-1] + (RepeatNode(node.items[-1], lo, hi),))
        return RepeatNode(node, lo, hi)

    def parse_seq(self, stop: str = "") -> Node:
        items: list[Node] = []
        while True:
            self.skip_ws()
            if self.eof() or self.peek() in stop:
                break
            n = self.parse_quantified()
            if n is None:
                break
            items.append(n)
        if len(items) == 1:
            return items[0]
        return SeqNode(tuple(items))


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Pattern:
    """コンパイル済みパターン."""

    root: Node
    source: str
    prohibitive: bool = False  # 先頭に '*' があった（markedness 制約）

    # -- 照合 -----------------------------------------------------------
    def match_at(self, seq: Sequence[Symbol], i: int) -> int | None:
        """位置 ``i`` から始まる最長マッチの終了位置．無ければ None."""
        best = None
        for e in self.root.match(seq, i):
            if best is None or e > best:
                best = e
        return best

    def find_all(self, seq: Sequence[Symbol]) -> list[tuple[int, int]]:
        """マッチする (start, end) をすべて返す（開始位置ごとに最長1件）.

        音節境界だけを消費する空マッチを数えないよう、開始位置は
        「境界でない位置」および語頭・語末に限る．
        """
        out = []
        for i in self._start_positions(seq):
            e = self.match_at(seq, i)
            if e is not None:
                out.append((i, e))
        return out

    @staticmethod
    def _start_positions(seq: Sequence[Symbol]) -> list[int]:
        return [
            i
            for i in range(len(seq) + 1)
            if i == len(seq)
            or not (isinstance(seq[i], BoundarySymbol) and seq[i].kind == "syllable")
        ]

    def count(self, seq: Sequence[Symbol]) -> int:
        """違反回数（マッチの開始位置の個数）."""
        return len(self.find_all(seq))

    def search(self, seq: Sequence[Symbol]) -> bool:
        return any(self.match_at(seq, i) is not None for i in self._start_positions(seq))

    def __str__(self) -> str:
        return self.source


def parse_pattern(text: str, inventory: "Inventory | None" = None) -> Pattern:
    """DSL 文字列をパターンにコンパイルする."""
    if inventory is None:
        from .inventory import inventory as _inv

        inventory = _inv()
    src = text.strip()
    prohibitive = src.startswith("*")
    body = src[1:] if prohibitive else src
    p = _Parser(body, inventory)
    root = p.parse_seq()
    p.skip_ws()
    if not p.eof():
        p.error("末尾に解釈できない文字がある")
    return Pattern(root, src, prohibitive)


def parse_segment_spec(
    text: str, inventory: "Inventory | None" = None, resolve_classes: bool = True
) -> SegmentSpec:
    """``[+cons]`` のような単一セグメント指定をパースする."""
    p = _Parser(text.strip(), inventory, resolve_classes)
    p.skip_ws()
    if p.peek() != "[":
        p.error("'[' で始まる必要がある")
    return p.parse_bracket_spec()


# ---------------------------------------------------------------------------
# 書き換え規則
# ---------------------------------------------------------------------------

_ZERO = {"0", "∅", "Ø", ""}


@dataclass(frozen=True)
class Rule:
    """``A -> B / C _ D`` 形式の書き換え規則."""

    name: str
    target: Pattern
    replacement: str  # 綴り字（空文字なら削除）
    left: Pattern | None
    right: Pattern | None
    source: str

    def structural_description(self, inventory: "Inventory") -> Pattern:
        """C A D を連結したパターン（適用文脈の検出用）."""
        parts = []
        if self.left:
            parts.append(self.left.source)
        parts.append(self.target.source)
        if self.right:
            parts.append(self.right.source)
        return parse_pattern("".join(parts), inventory)

    def __str__(self) -> str:
        return self.source


def parse_rule(text: str, name: str = "", inventory: "Inventory | None" = None) -> Rule:
    if inventory is None:
        from .inventory import inventory as _inv

        inventory = _inv()
    src = text.strip()
    if "->" not in src and "→" not in src:
        raise ParseError(f"'->' がない: {src!r}")
    arrow = "->" if "->" in src else "→"
    lhs, _, rest = src.partition(arrow)
    if "/" in rest:
        rhs, _, ctx = rest.partition("/")
    else:
        rhs, ctx = rest, ""
    rhs = rhs.strip()
    left = right = None
    if ctx.strip():
        if "_" not in ctx:
            raise ParseError(f"文脈に '_' がない: {ctx!r}")
        lc, _, rc = ctx.partition("_")
        left = parse_pattern(lc.strip(), inventory) if lc.strip() else None
        right = parse_pattern(rc.strip(), inventory) if rc.strip() else None
    return Rule(
        name=name,
        target=parse_pattern(lhs.strip(), inventory),
        replacement="" if rhs in _ZERO else rhs,
        left=left,
        right=right,
        source=src,
    )
