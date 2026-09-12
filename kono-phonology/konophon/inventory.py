"""音素目録・素性・トークン化.

`phonology.toml` を唯一の定義元として読み込み、以下を提供する:

- :class:`Phoneme`  … 不変・インターン済みの音素オブジェクト
- :class:`Inventory` … 音素目録全体（素性、自然類、IPA、制約表）
- :func:`inventory`  … 既定の目録（シングルトン）

素性値は次の3種類のいずれか:
    bool          二値素性 (+cons など)
    str           カテゴリ素性 (place=labial)
    int/float     スカラー素性 (sonor=7)
"""

from __future__ import annotations

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # 3.10 以下
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        from . import _minitoml as tomllib  # type: ignore[no-redef]

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_TOML = DATA_DIR / "phonology.toml"

FeatureValue = bool | str | int | float


@dataclass(frozen=True, slots=True)
class Phoneme:
    """音素. 綴り字 (``spell``) が同一性の基準."""

    spell: str
    ipa: str
    features: Mapping[str, FeatureValue]
    alt: tuple[str, ...] = ()
    note: str = ""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.spell

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"/{self.spell}/"

    def __hash__(self) -> int:
        return hash(self.spell)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Phoneme):
            return self.spell == other.spell
        if isinstance(other, str):
            return self.spell == other
        return NotImplemented

    # -- 素性アクセス ---------------------------------------------------
    def get(self, name: str, default: Any = None) -> Any:
        return self.features.get(name, default)

    def __getitem__(self, name: str) -> FeatureValue:
        return self.features[name]

    def has(self, name: str, value: FeatureValue) -> bool:
        """素性 ``name`` の値が ``value`` と一致するか."""
        return self.features.get(name, None) == value

    # -- よく使う述語 ---------------------------------------------------
    @property
    def is_vowel(self) -> bool:
        return bool(self.features.get("syl"))

    @property
    def is_consonant(self) -> bool:
        return bool(self.features.get("cons"))

    @property
    def sonority(self) -> float:
        return float(self.features.get("sonor", 0))

    @property
    def manner(self) -> str:
        return str(self.features.get("manner", ""))

    @property
    def place(self) -> str:
        return str(self.features.get("place", ""))


# 素性宣言 ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    name: str
    type: str  # binary | privative | categorical | scalar
    doc: str = ""
    values: tuple[str, ...] = ()


@dataclass
class Inventory:
    """音素目録．TOML から構築する．"""

    raw: dict[str, Any]
    phonemes: tuple[Phoneme, ...]
    feature_specs: dict[str, FeatureSpec]
    class_defs: dict[str, str]

    # ------------------------------------------------------------------
    @classmethod
    def load(cls, path: str | Path = DEFAULT_TOML) -> "Inventory":
        raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))

        specs: dict[str, FeatureSpec] = {}
        for name, d in raw.get("features", {}).items():
            specs[name] = FeatureSpec(
                name=name,
                type=d.get("type", "binary"),
                doc=d.get("doc", ""),
                values=tuple(d.get("values", ())),
            )

        known = set(specs) | {"spell", "ipa", "alt", "note"}
        phonemes = []
        for d in raw.get("phonemes", []):
            unknown = set(d) - known
            if unknown:
                raise ValueError(f"{d['spell']}: 未宣言の素性 {sorted(unknown)}")
            feats = {k: v for k, v in d.items() if k in specs}
            phonemes.append(
                Phoneme(
                    spell=d["spell"],
                    ipa=d.get("ipa", d["spell"]),
                    features=dict(feats),
                    alt=tuple(d.get("alt", ())),
                    note=d.get("note", ""),
                )
            )

        return cls(
            raw=raw,
            phonemes=tuple(phonemes),
            feature_specs=specs,
            class_defs=dict(raw.get("classes", {})),
        )

    # -- 基本アクセス ---------------------------------------------------
    @cached_property
    def by_spell(self) -> dict[str, Phoneme]:
        return {p.spell: p for p in self.phonemes}

    def __getitem__(self, spell: str) -> Phoneme:
        return self.by_spell[spell]

    def __contains__(self, spell: object) -> bool:
        return spell in self.by_spell

    def __iter__(self) -> Iterator[Phoneme]:
        return iter(self.phonemes)

    def __len__(self) -> int:
        return len(self.phonemes)

    @cached_property
    def consonants(self) -> tuple[Phoneme, ...]:
        return tuple(p for p in self.phonemes if p.is_consonant)

    @cached_property
    def vowels(self) -> tuple[Phoneme, ...]:
        return tuple(p for p in self.phonemes if p.is_vowel)

    @cached_property
    def _longest_first(self) -> tuple[str, ...]:
        return tuple(sorted(self.by_spell, key=len, reverse=True))

    # -- トークン化 -----------------------------------------------------
    def tokenize(self, text: str, *, strict: bool = True) -> list[Phoneme] | None:
        """綴り字を最長一致で音素列に分解する．

        ``strict=True`` なら分解できない場合に ``ValueError``、
        ``strict=False`` なら ``None`` を返す．
        """
        out: list[Phoneme] = []
        i = 0
        while i < len(text):
            for s in self._longest_first:
                if text.startswith(s, i):
                    out.append(self.by_spell[s])
                    i += len(s)
                    break
            else:
                if strict:
                    raise ValueError(f"トークン化失敗: {text!r} の位置 {i} ({text[i]!r})")
                return None
        return out

    # -- 自然類 ---------------------------------------------------------
    @cached_property
    def classes(self) -> dict[str, frozenset[Phoneme]]:
        """略号 -> 音素集合．``class_defs`` の素性式を評価して構築する."""
        from .dsl import parse_segment_spec  # 循環 import 回避のため遅延

        out: dict[str, frozenset[Phoneme]] = {}
        for name, expr in self.class_defs.items():
            spec = parse_segment_spec(expr, inventory=self, resolve_classes=False)
            out[name] = frozenset(p for p in self.phonemes if spec.matches_phoneme(p))
        return out

    def natural_class(self, name: str) -> frozenset[Phoneme]:
        return self.classes[name]

    def class_of(self, ph: Phoneme, names: Iterable[str] = ("S", "Q", "T", "N", "L", "J", "V")) -> str:
        """音素が属する（最初にマッチする）自然類の略号を返す."""
        for n in names:
            if n in self.classes and ph in self.classes[n]:
                return n
        return "?"

    # -- 制約表 ---------------------------------------------------------
    @cached_property
    def syllable_cfg(self) -> dict[str, Any]:
        return self.raw.get("syllable", {})

    def _pair_table(self, key: str, by_class: bool) -> frozenset[tuple[str, str]]:
        table = self.syllable_cfg.get(key, {})
        out: set[tuple[str, str]] = set()
        for lhs, rhss in table.items():
            lefts = [p.spell for p in self.classes[lhs]] if by_class else [lhs]
            for rhs in rhss:
                rights = [p.spell for p in self.classes[rhs]] if by_class else [rhs]
                out.update((a, b) for a in lefts for b in rights)
        return frozenset(out)

    @cached_property
    def legal_onset_pairs(self) -> frozenset[tuple[str, str]]:
        return self._pair_table("onset_pairs", by_class=True)

    @cached_property
    def legal_coda_pairs(self) -> frozenset[tuple[str, str]]:
        return self._pair_table("coda_pairs", by_class=True)

    @cached_property
    def legal_nucleus_pairs(self) -> frozenset[tuple[str, str]]:
        return self._pair_table("nucleus_pairs", by_class=False)

    # -- 韻律設定 -------------------------------------------------------
    @cached_property
    def prosody_cfg(self) -> dict[str, Any]:
        return self.raw.get("prosody", {})

    @cached_property
    def phonetics_cfg(self) -> dict[str, Any]:
        return self.raw.get("phonetics", {})

    @cached_property
    def spelling_rules(self) -> list[tuple[str, dict[str, str]]]:
        return [
            (r["name"], dict(r.get("map", {})))
            for r in self.raw.get("rules", [])
            if r.get("type") == "spelling"
        ]

    @cached_property
    def declared_constraints(self) -> list[dict[str, Any]]:
        return list(self.raw.get("constraints", []))


_DEFAULT: Inventory | None = None


def inventory(path: str | Path | None = None) -> Inventory:
    """既定の音素目録（シングルトン）を返す."""
    global _DEFAULT
    if path is not None:
        return Inventory.load(path)
    if _DEFAULT is None:
        _DEFAULT = Inventory.load()
    return _DEFAULT
