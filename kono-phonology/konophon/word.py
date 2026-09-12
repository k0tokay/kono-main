"""語 — 音素列・音節化・アクセントを束ねた分析単位.

``Word`` は次の 2 つの tier を提供し、どちらにも同じ DSL パターンを
適用できる:

``segment_tier()``
    音素を並べ、語境界 ``#`` と音節境界 ``.`` を差し込んだ列．
    各音素には所属する音節の位置情報（``role``, ``syl_index``,
    ``initial``/``final``/``penult``, ``accent``）が注入されるので、
    ``[+cons, role=coda]`` のような指定が書ける．

``syllable_tier()``
    音節をシンボルとする列．``[weight=heavy, penult=true]`` のような
    韻律的な制約が書ける．
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, Iterable, Iterator, Mapping, Sequence

from .dsl import SYLLABLE_BOUNDARY, WORD_BOUNDARY, Pattern, Symbol, parse_pattern
from .inventory import Inventory, Phoneme, inventory as default_inventory
from .prosody import RIME, AccentPattern, WeightScale, check_contour_licensing, get_scale
from .seq import Seq
from .syllable import Syllabifier, Syllable, SyllabifyError, split_boundaries


@dataclass(frozen=True)
class Segment:
    """音節内での位置情報を帯びた音素（segment tier のシンボル）."""

    phoneme: Phoneme
    _features: dict[str, Any] = field(repr=False)

    @property
    def spell(self) -> str:
        return self.phoneme.spell

    @property
    def ipa(self) -> str:
        return self.phoneme.ipa

    @property
    def features(self) -> Mapping[str, Any]:
        return self._features

    def __str__(self) -> str:
        return self.phoneme.spell

    def __repr__(self) -> str:  # pragma: no cover
        return f"/{self.phoneme.spell}:{self._features.get('role')}/"


class Word:
    """分析単位としての語.

    Parameters
    ----------
    source
        綴り字（``naz.loft`` のように ``.`` / ``|`` で強制境界を書ける）、
        ``Seq``、または音素の列．
    accent
        ``"HLL"`` のようなアクセント列（任意）．
    gloss
        訳語などのメモ（任意）．
    """

    __slots__ = ("seq", "syllables", "accent", "gloss", "inv", "forced", "meta", "notes", "__dict__")

    def __init__(
        self,
        source: "str | Seq | Iterable[Phoneme]",
        *,
        accent: "str | AccentPattern | None" = None,
        gloss: str = "",
        inv: Inventory | None = None,
        syllabifier: Syllabifier | None = None,
        syllables: Sequence[Syllable] | None = None,
        meta: Mapping[str, Any] | None = None,
    ):
        self.inv = inv or (source.inv if isinstance(source, Seq) else default_inventory())
        if isinstance(source, str):
            self.seq, self.forced = split_boundaries(source, self.inv)
        else:
            self.seq, self.forced = Seq.of(source, self.inv), frozenset()
        self.gloss = gloss
        self.meta = dict(meta or {})

        if syllables is not None:
            self.syllables = list(syllables)
            self.notes: list[str] = []
        else:
            sylr = syllabifier or Syllabifier(self.inv)
            self.syllables, self.notes = sylr.parse(self.seq, self.forced)

        if accent is None:
            self.accent = None
        else:
            ap = accent if isinstance(accent, AccentPattern) else AccentPattern.parse(accent)
            if len(ap) != len(self.syllables):
                raise ValueError(
                    f"{self.spell}: アクセント長 {len(ap)} != 音節数 {len(self.syllables)} "
                    f"({self.syllabified})"
                )
            self.accent = ap
            self.syllables = [s.with_(accent=a) for s, a in zip(self.syllables, ap)]

    # -- 構築ヘルパ -----------------------------------------------------
    @classmethod
    def try_make(cls, source, **kw) -> "Word | None":
        try:
            return cls(source, **kw)
        except (ValueError, SyllabifyError):
            return None

    # -- 表記 -----------------------------------------------------------
    @property
    def spell(self) -> str:
        return self.seq.spell

    @property
    def syllabified(self) -> str:
        return ".".join(s.spell for s in self.syllables)

    @property
    def ipa(self) -> str:
        from .phonetics import to_ipa

        return to_ipa(self.seq)

    def __str__(self) -> str:
        return self.spell

    def __repr__(self) -> str:  # pragma: no cover
        a = f" {self.accent}" if self.accent else ""
        return f"<Word {self.syllabified}{a}>"

    def __len__(self) -> int:
        return len(self.seq)

    def __eq__(self, other) -> bool:
        if isinstance(other, Word):
            return self.seq == other.seq and self.syllabified == other.syllabified
        if isinstance(other, str):
            return self.spell == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self.seq, self.syllabified))

    # -- tier -----------------------------------------------------------
    @cached_property
    def segments(self) -> list[Segment]:
        out: list[Segment] = []
        n = len(self.syllables)
        for si, syl in enumerate(self.syllables):
            pos = {
                "syl_index": si,
                "from_end": n - si,
                "initial": si == 0,
                "final": si == n - 1,
                "penult": si == n - 2,
                "syl_weight": RIME.weight_class(syl),
                "syl_mora": RIME.mora(syl),
                "accent": syl.accent or None,
                "syl_shape": syl.shape,
            }
            for role, part in (("onset", syl.onset), ("nucleus", syl.nucleus), ("coda", syl.coda)):
                for k, ph in enumerate(part):
                    f = dict(ph.features)
                    f["spell"] = ph.spell
                    f.update(pos)
                    f["role"] = role
                    f["role_index"] = k
                    f["word_initial"] = si == 0 and role == "onset" and k == 0
                    out.append(Segment(ph, f))
        return out

    def segment_tier(self) -> list[Symbol]:
        """音素列 + 語境界 + 音節境界."""
        out: list[Symbol] = [WORD_BOUNDARY]
        for si, syl in enumerate(self.syllables):
            if si:
                out.append(SYLLABLE_BOUNDARY)
            out.extend(s for s in self.segments if s.features["syl_index"] == si)
        out.append(WORD_BOUNDARY)
        return out

    def syllable_tier(self) -> list[Symbol]:
        return [WORD_BOUNDARY, *self.syllables, WORD_BOUNDARY]

    def tier(self, name: str = "segment") -> list[Symbol]:
        if name in ("segment", "seg", "phoneme"):
            return self.segment_tier()
        if name in ("syllable", "syl", "sigma"):
            return self.syllable_tier()
        raise KeyError(f"未知の tier: {name!r}")

    # -- 照合 -----------------------------------------------------------
    def _pat(self, pattern: "Pattern | str") -> Pattern:
        return pattern if isinstance(pattern, Pattern) else parse_pattern(pattern, self.inv)

    def matches(self, pattern: "Pattern | str", tier: str = "segment") -> bool:
        return self._pat(pattern).search(self.tier(tier))

    def count(self, pattern: "Pattern | str", tier: str = "segment") -> int:
        return self._pat(pattern).count(self.tier(tier))

    def find_all(self, pattern: "Pattern | str", tier: str = "segment"):
        return self._pat(pattern).find_all(self.tier(tier))

    # -- 韻律 -----------------------------------------------------------
    def moras(self, scale: "str | WeightScale" = RIME) -> list[int]:
        sc = get_scale(scale, self.inv)
        return [sc.mora(s) for s in self.syllables]

    def total_mora(self, scale: "str | WeightScale" = RIME) -> int:
        return sum(self.moras(scale))

    def weights(self, scale: "str | WeightScale" = RIME) -> list[str]:
        sc = get_scale(scale, self.inv)
        return [sc.weight_class(s) for s in self.syllables]

    def contour_problems(self, scale: "str | WeightScale" = RIME) -> list[str]:
        """F/R が 2μ 要件を満たさない音節を列挙する."""
        if self.accent is None:
            return []
        sc = get_scale(scale, self.inv)
        req = int(self.inv.prosody_cfg.get("fall_requires_mora", 2))
        return check_contour_licensing(self.syllables, self.accent, sc, req)

    @property
    def n_syllables(self) -> int:
        return len(self.syllables)

    # -- 便利 -----------------------------------------------------------
    @cached_property
    def shape(self) -> str:
        return ".".join(s.shape for s in self.syllables)

    @cached_property
    def cv_skeleton(self) -> str:
        return self.seq.cv_skeleton

    def to_dict(self) -> dict[str, Any]:
        return {
            "spell": self.spell,
            "syllabified": self.syllabified,
            "accent": str(self.accent) if self.accent else "",
            "gloss": self.gloss,
            "n_syllables": self.n_syllables,
            "shape": self.shape,
            "mora_rime": self.moras("rime"),
            "mora_onset_sensitive": self.moras("onset_sensitive"),
            "ipa": self.ipa,
            "notes": "; ".join(self.notes),
            **self.meta,
        }
