"""音声実現（綴り字 -> IPA）.

``phonology.tex`` 「綴り字と発音の乖離」に対応．規則は
``phonology.toml`` の ``[phonetics]`` に置かれている．

注意: 「単母音で書かれていても伸ばして発音される」（アクセント連動の
長音化）はここでは扱わない．あれは語彙ごとの韻律的事実であり、
:class:`~konophon.word.Word` の音節化（``lii.flom`` のような表記）で
与えるべきものである．
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .inventory import Inventory, inventory as default_inventory

if TYPE_CHECKING:  # pragma: no cover
    from .seq import Seq


def _fusion(inv: Inventory) -> dict[str, str]:
    return dict(inv.phonetics_cfg.get("vowel_fusion", {}))


def to_ipa(seq: "Seq", *, apply_processes: bool = True) -> str:
    """音素列を IPA 文字列にする."""
    inv = seq.inv
    fus = _fusion(inv)
    out: list[str] = []
    i = 0
    n = len(seq)
    while i < n:
        p = seq[i]
        if p.is_vowel and i + 1 < n and seq[i + 1].is_vowel:
            pair = p.spell + seq[i + 1].spell
            if pair in fus:
                out.append(fus[pair])
                i += 2
                continue
        out.append(p.ipa)
        i += 1

    if apply_processes:
        # 語末の単独破裂音 -> [ʔ]
        if n and seq[-1].manner == "plosive":
            if n == 1 or not seq[-2].is_consonant:
                out[-1] = "ʔ"
            elif seq[-2].manner == "nasal":
                out[-2:] = ["ʔ"]
    return "".join(out)


def ipa_table(inv: Inventory | None = None) -> list[dict[str, str]]:
    """音素 -> IPA の一覧（tex 表生成・照合用）."""
    inv = inv or default_inventory()
    return [
        {
            "spell": p.spell,
            "ipa": p.ipa,
            "alt": "~".join(p.alt),
            "manner": p.manner,
            "place": p.place,
            "note": p.note,
        }
        for p in inv
    ]
