"""語彙の読み込み.

対応形式:

- ``konomeno-v5.json``（正典．``語彙`` サブツリーのみを既定で取る）
- zpdic 形式（``saimeno-v4.json`` など）
- ``accent/data.tsv``（音節化・アクセント注釈つき）
- プレーンな単語リスト（1行1語）
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from .inventory import Inventory, inventory as default_inventory
from .syllable import SyllabifyError
from .word import Word

LATIN = re.compile(r"[a-z]+")


@dataclass
class Corpus:
    """語の集まり．読み込み時に失敗した語は ``rejected`` に入る."""

    words: list[Word] = field(default_factory=list)
    rejected: list[tuple[str, str]] = field(default_factory=list)
    name: str = ""
    inv: Inventory = field(default_factory=default_inventory)

    def __len__(self) -> int:
        return len(self.words)

    def __iter__(self) -> Iterator[Word]:
        return iter(self.words)

    def __getitem__(self, i):
        return self.words[i] if isinstance(i, int) else Corpus(self.words[i], [], self.name, self.inv)

    def filter(self, pred) -> "Corpus":
        return Corpus([w for w in self.words if pred(w)], [], self.name, self.inv)

    def with_accent(self) -> "Corpus":
        return self.filter(lambda w: w.accent is not None)

    def to_frame(self):
        import pandas as pd

        return pd.DataFrame([w.to_dict() for w in self.words])

    def report(self) -> str:
        lines = [f"[{self.name}] {len(self.words)} 語（除外 {len(self.rejected)} 語）"]
        for spell, why in self.rejected[:20]:
            lines.append(f"  - {spell}: {why}")
        if len(self.rejected) > 20:
            lines.append(f"  ... 他 {len(self.rejected) - 20} 件")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    @classmethod
    def from_iterable(
        cls,
        items: Iterable[str | tuple[str, dict[str, Any]]],
        name: str = "",
        inv: Inventory | None = None,
    ) -> "Corpus":
        inv = inv or default_inventory()
        words, bad = [], []
        for it in items:
            spell, meta = (it, {}) if isinstance(it, str) else it
            try:
                words.append(
                    Word(
                        spell,
                        inv=inv,
                        accent=meta.pop("accent", None) or None,
                        gloss=meta.pop("gloss", ""),
                        meta=meta,
                    )
                )
            except (ValueError, SyllabifyError, KeyError) as e:
                bad.append((spell, str(e)))
        return cls(words, bad, name, inv)


# ---------------------------------------------------------------------------
# ローダ
# ---------------------------------------------------------------------------


def load_v5(path: str | Path, root: str | None = "語彙", inv: Inventory | None = None) -> Corpus:
    """konomeno-v5.json（正典）から見出し語を読む."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    words = [w for w in data["words"] if w]
    if root is not None:
        byid = {w["id"]: w for w in words}
        keep: set = set()
        stack = [w["id"] for w in words if w.get("entry") == root and not w.get("upper_covers")]
        while stack:
            i = stack.pop()
            if i in keep:
                continue
            keep.add(i)
            stack.extend(byid[i].get("lower_covers", []))
        words = [byid[i] for i in keep if i in byid]
    forms = sorted({w["entry"] for w in words if w.get("entry") and LATIN.fullmatch(w["entry"])})
    return Corpus.from_iterable(forms, name=Path(path).stem, inv=inv)


def load_zpdic(path: str | Path, inv: Inventory | None = None) -> Corpus:
    """zpdic 形式の辞書を読む."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = []
    for w in data["words"]:
        if not w:
            continue
        form = w["entry"]["form"]
        if LATIN.fullmatch(form):
            items.append((form, {"gloss": (w.get("translations") or [{}])[0].get("forms", [""])[0]}))
    return Corpus.from_iterable(items, name=Path(path).stem, inv=inv)


def load_accent_tsv(path: str | Path, inv: Inventory | None = None) -> Corpus:
    """``accent/data.tsv`` を読む.

    列: 単語 / 翻訳 / 音節化・長短 / 高低 / 確信度

    ``音節化・長短`` は ``|`` で複数案が書かれることがある（第1案を採用し、
    残りは ``meta['alt_syllabification']`` に入れる）．表記に無い長母音
    （``eto`` → ``e.too``）が書かれている場合、その形を実際の音形とみなし、
    ``meta['lengthened']`` に伸びた音節の index を記録する．
    """
    inv = inv or default_inventory()
    rows = list(csv.DictReader(Path(path).open(encoding="utf-8"), delimiter="\t"))
    items = []
    for r in rows:
        spell = (r.get("単語") or "").strip()
        if not spell:
            continue
        syl_field = (r.get("音節化・長短") or "").strip()
        acc_field = (r.get("高低") or "").strip()
        if not syl_field or not acc_field:
            continue
        syls = [s.strip() for s in syl_field.split("|") if s.strip()]
        accs = [a.strip() for a in acc_field.split("|") if a.strip()]
        surface = syls[0]
        meta = {
            "underlying": spell,
            "gloss": (r.get("翻訳") or "").strip(),
            "confidence": (r.get("確信度") or "").strip(),
            "alt_syllabification": syls[1:],
            "alt_accent": accs[1:],
            "lengthened": _lengthened_indices(spell, surface),
        }
        items.append((surface, {**meta, "accent": accs[0]}))
    return Corpus.from_iterable(items, name=Path(path).stem, inv=inv)


def _lengthened_indices(underlying: str, surface: str) -> list[int]:
    """綴りに無い長母音が現れた音節の index を返す."""
    out = []
    ul_doubles = set(re.findall(r"([aoeiyuv])\1", underlying))
    for i, s in enumerate(surface.split(".")):
        m = re.search(r"([aoeiyuv])\1", s)
        if m and m.group(1) not in ul_doubles:
            out.append(i)
    return out


def load_wordlist(path: str | Path, inv: Inventory | None = None) -> Corpus:
    lines = [l.strip() for l in Path(path).read_text(encoding="utf-8").splitlines()]
    return Corpus.from_iterable(
        [l for l in lines if l and not l.startswith("#") and LATIN.fullmatch(l)],
        name=Path(path).stem,
        inv=inv,
    )


def autoload(path: str | Path, inv: Inventory | None = None) -> Corpus:
    """拡張子と中身から形式を推測して読む."""
    p = Path(path)
    if p.suffix == ".tsv":
        return load_accent_tsv(p, inv)
    if p.suffix == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        w0 = next((w for w in data.get("words", []) if w), {})
        return load_zpdic(p, inv) if isinstance(w0.get("entry"), dict) else load_v5(p, inv=inv)
    return load_wordlist(p, inv)
