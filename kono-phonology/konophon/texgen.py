"""phonology.tex の表を phonology.toml から生成する.

手書きの表とコードの定義が二重管理になるのを防ぐための出力側．
``scripts/gen_tex_tables.py`` から呼ばれる．
"""

from __future__ import annotations

from .inventory import Inventory, inventory as default_inventory

MANNER_JA = {
    "fricative": "摩擦音",
    "affricate": "破擦音",
    "plosive": "破裂音",
    "nasal": "鼻音",
    "liquid": "流音",
    "approximant": "接近音",
}
PLACE_JA = {
    "labial": "唇音",
    "alveolar": "歯茎音",
    "postalveolar": "後部歯茎音",
    "palatal": "硬口蓋音",
    "velar": "軟口蓋音",
    "glottal": "声門音",
}
CLASS_ORDER = ["S", "Q", "T", "N", "L", "J"]
EMPTY = "\\_"


def _table(caption: str, header: list[str], rows: list[list[str]]) -> str:
    cols = "c" * len(header)
    body = "\n".join("      " + " & ".join(r) + r"\\" for r in rows)
    return (
        "\\begin{table}[H]\n"
        f"  \\caption{{{caption}}}\n"
        "    \\centering\n"
        f"    \\begin{{tabular}}{{{cols}}}\n"
        "      \\toprule\n"
        f"      {' & '.join(header)}\\\\\n"
        "      \\midrule\n"
        f"{body}\n"
        "      \\bottomrule\n"
        "    \\end{tabular}\n"
        "\\end{table}"
    )


def consonant_table(inv: Inventory | None = None) -> str:
    inv = inv or default_inventory()
    places = [p for p in PLACE_JA if any(c.place == p for c in inv.consonants)]
    manners = [m for m in MANNER_JA if any(c.manner == m for c in inv.consonants)]
    rows = []
    for m in manners:
        cells = []
        for pl in places:
            here = [c for c in inv.consonants if c.manner == m and c.place == pl]
            vl = next((c.spell for c in here if not c.get("voi")), None)
            vd = next((c.spell for c in here if c.get("voi")), None)
            if not here:
                cells.append("")
            elif m in ("nasal", "liquid", "approximant"):
                cells.append(here[0].spell)
            else:
                cells.append(f"{vl or EMPTY}\\ {vd or EMPTY}")
        rows.append([MANNER_JA[m]] + cells)
    return _table("子音の一覧", [""] + [PLACE_JA[p] for p in places], rows)


def vowel_table(inv: Inventory | None = None) -> str:
    inv = inv or default_inventory()
    rows = []
    def zone(v):
        if v.get("central") and not v.get("high"):
            return "中舌"
        return "後舌" if v.get("back") else "前舌"

    for label, pred in (
        ("狭", lambda v: v.get("high") and not v.get("low")),
        ("中", lambda v: not v.get("high") and not v.get("low")),
        ("広", lambda v: v.get("low")),
    ):
        cells = []
        for z in ("前舌", "中舌", "後舌"):
            here = [v for v in inv.vowels if pred(v) and zone(v) == z]
            if not here:
                cells.append("")
                continue
            unr = next((v.spell for v in here if not v.get("round")), None)
            rnd = next((v.spell for v in here if v.get("round")), None)
            cells.append(f"{unr or EMPTY}\\ {rnd or EMPTY}")
        rows.append([label] + cells)
    return _table("母音の一覧", ["", "前舌", "中舌", "後舌"], rows)


def _pair_table(caption: str, allowed: dict[str, list[str]], order=CLASS_ORDER, label="") -> str:
    rows = []
    for a in order:
        rows.append([a] + ["○" if b in allowed.get(a, []) else "" for b in order])
    return _table(caption, [label] + order, rows)


def onset_table(inv: Inventory | None = None) -> str:
    inv = inv or default_inventory()
    return _pair_table(
        "$\\omega$の制約",
        inv.syllable_cfg.get("onset_pairs", {}),
        label="$\\omega_0$＼$\\omega_1$",
    )


def coda_table(inv: Inventory | None = None) -> str:
    inv = inv or default_inventory()
    return _pair_table(
        "$\\kappa$の制約",
        inv.syllable_cfg.get("coda_pairs", {}),
        label="$\\kappa_0$＼$\\kappa_1$",
    )


def nucleus_table(inv: Inventory | None = None) -> str:
    inv = inv or default_inventory()
    order = [v.spell for v in inv.vowels]
    return _pair_table(
        "$\\nu$の制約",
        inv.syllable_cfg.get("nucleus_pairs", {}),
        order=order,
        label="$\\nu_1$＼$\\nu_2$",
    )


def all_tables(inv: Inventory | None = None) -> str:
    inv = inv or default_inventory()
    parts = [
        "% !! 自動生成 — konophon/data/phonology.toml を編集して",
        "% !! scripts/gen_tex_tables.py を再実行すること",
        consonant_table(inv),
        vowel_table(inv),
        onset_table(inv),
        nucleus_table(inv),
        coda_table(inv),
    ]
    return "\n\n".join(parts) + "\n"
