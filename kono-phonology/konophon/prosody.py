"""韻律 — 重さスケール・モーラ・アクセント記号.

**重さスケールは差し替え可能である**ことが設計の要点．
``phonology.tex`` 準拠の ``rime`` スケール（オンセットは寄与しない）と、
オンセットの複雑さを勘定に入れる ``onset_sensitive`` スケールを
同時に持ち、同じ語彙に対して両方を計算して比較できるようにしてある．

これは次の 2 機構モデルを検証するための仕組みである:

1. **プロミネンス**（アクセント位置の決定）… オンセットを含む重さで計算
2. **モーラ**（F の実現可能性）… ライムのみ．F には 2μ 必要

根拠となる観察: ``pakata`` (HHH) vs ``paklata`` (LFL) はオンセットの
複雑さだけが異なる．また ``kwilwa`` (FR) は ``rime`` スケールでは
軽音節に F が乗る例外だが、``onset_sensitive`` では例外でなくなる．
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:  # pragma: no cover
    from .inventory import Inventory
    from .syllable import Syllable

ACCENTS = ("H", "L", "F", "R")
CONTOUR_ACCENTS = frozenset({"F", "R"})


@dataclass(frozen=True, slots=True)
class WeightScale:
    """音節のモーラ数を計算する規則．"""

    name: str
    nucleus_short: int = 1
    nucleus_long: int = 2
    per_coda_consonant: int = 1
    per_extra_onset_consonant: int = 0
    license_with_onset: bool = False
    doc: str = ""

    def mora(self, syl: "Syllable") -> int:
        n = self.nucleus_long if len(syl.nucleus) >= 2 else self.nucleus_short
        n += self.per_coda_consonant * len(syl.coda)
        n += self.per_extra_onset_consonant * max(0, len(syl.onset) - 1)
        return n

    def licensing_mora(self, syl: "Syllable") -> int:
        """輪郭調 (F/R) を担えるかの判定に使うモーラ数.

        既定ではライムのみ（オンセットは輪郭調をホストできない）．
        ``license_with_onset=True`` のスケールではオンセットも算入する
        ＝「オンセットも輪郭調をホストできる」という対立仮説になる．
        """
        if self.license_with_onset:
            return self.mora(syl)
        n = self.nucleus_long if len(syl.nucleus) >= 2 else self.nucleus_short
        return n + self.per_coda_consonant * len(syl.coda)

    #: 後方互換の別名
    rime_mora = licensing_mora

    def weight_class(self, syl: "Syllable") -> str:
        m = self.mora(syl)
        if m <= 1:
            return "light"
        if m == 2:
            return "heavy"
        return "superheavy"


#: tex 準拠（既定）
RIME = WeightScale("rime", doc="phonology.tex 準拠．ライムのみ")

#: オンセット第2子音以降を +1 する仮説的スケール（Ryan 2014 型）
ONSET_SENSITIVE = WeightScale(
    "onset_sensitive",
    per_extra_onset_consonant=1,
    license_with_onset=True,
    doc="オンセットの複雑さを重さに算入する仮説",
)

_BUILTIN = {s.name: s for s in (RIME, ONSET_SENSITIVE)}


def scales_from(inv: "Inventory") -> dict[str, WeightScale]:
    """phonology.toml の ``[prosody.scales.*]`` からスケールを構築する."""
    out = dict(_BUILTIN)
    for name, d in inv.prosody_cfg.get("scales", {}).items():
        out[name] = WeightScale(
            name=name,
            nucleus_short=d.get("nucleus_short", 1),
            nucleus_long=d.get("nucleus_long", 2),
            per_coda_consonant=d.get("per_coda_consonant", 1),
            per_extra_onset_consonant=d.get("per_extra_onset_consonant", 0),
            license_with_onset=d.get("license_with_onset", False),
            doc=d.get("doc", ""),
        )
    return out


def get_scale(name: str | WeightScale, inv: "Inventory | None" = None) -> WeightScale:
    if isinstance(name, WeightScale):
        return name
    if inv is not None:
        return scales_from(inv)[name]
    return _BUILTIN[name]


# ---------------------------------------------------------------------------
# アクセント列
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AccentPattern:
    """音節ごとのアクセント記号列（例 ``HLL``）."""

    symbols: tuple[str, ...]

    @classmethod
    def parse(cls, text: str) -> "AccentPattern":
        s = text.strip()
        bad = set(s) - set(ACCENTS)
        if bad:
            raise ValueError(f"未知のアクセント記号: {sorted(bad)}")
        return cls(tuple(s))

    def __len__(self) -> int:
        return len(self.symbols)

    def __getitem__(self, i):
        return self.symbols[i]

    def __iter__(self):
        return iter(self.symbols)

    def __str__(self) -> str:
        return "".join(self.symbols)

    # -- 記述的な指標 ---------------------------------------------------
    @property
    def n_falls(self) -> int:
        """下降の回数（音節内 F ＋ 音節間 H->L）."""
        n = sum(1 for s in self.symbols if s == "F")
        for a, b in zip(self.symbols, self.symbols[1:]):
            if a in ("H", "F") and b == "L" and a != "F":
                n += 1
        return n

    @property
    def fall_index(self) -> int | None:
        """最初の下降を担う音節の index（無ければ None）."""
        for i, s in enumerate(self.symbols):
            if s == "F":
                return i
            if s == "H" and i + 1 < len(self.symbols) and self.symbols[i + 1] == "L":
                return i
        return None

    def index_from_end(self, i: int) -> int:
        """末尾からの位置（1 = 語末, 2 = penult）."""
        return len(self.symbols) - i

    @property
    def contour_indices(self) -> tuple[int, ...]:
        return tuple(i for i, s in enumerate(self.symbols) if s in CONTOUR_ACCENTS)


def check_contour_licensing(
    syllables, accents: AccentPattern, scale: WeightScale, required: int = 2
) -> list[str]:
    """輪郭調 (F/R) が必要モーラ数を満たしているか検査し、違反の説明を返す."""
    problems = []
    for i, (syl, a) in enumerate(zip(syllables, accents)):
        if a in CONTOUR_ACCENTS and scale.licensing_mora(syl) < required:
            problems.append(
                f"σ{i + 1} ({syl}) は {a} を担うが {scale.licensing_mora(syl)}μ < {required}μ"
            )
    return problems
