"""予備 TOML パーサが tomllib と完全に一致することを検証する.

``konophon/_minitoml.py`` は Python 3.10 以下で ``tomli`` も無い環境の
ための最小実装なので、正しさは「標準パーサと同じ結果を返すこと」で
担保する．3.11 未満ではこのテストは自動的にスキップされる．
"""

import sys

import pytest

from konophon import _minitoml
from konophon.inventory import DEFAULT_TOML

tomllib = pytest.importorskip("tomllib", reason="Python 3.11+ でのみ照合できる")


def test_matches_tomllib_on_phonology_toml():
    text = DEFAULT_TOML.read_text(encoding="utf-8")
    assert _minitoml.loads(text) == tomllib.loads(text)


@pytest.mark.parametrize(
    "src",
    [
        'a = 1\nb = "x"\nc = true\n',
        "[t]\nx = [1, 2, 3]\n",
        '[t]\nx = ["a", "b"]  # コメント\n',
        'f = { type = "binary", doc = "説明" }\n',
        "[[p]]\nspell = \"f\"\n\n[[p]]\nspell = \"s\"\n",
        "[a.b.c]\nx = 1.5\n",
        'x = [\n  "a",\n  "b",\n]\n',
        'quoted = "a # not a comment"\n',
        "neg = -3\nexp = 1e3\n",
        '[phonetics.vowel_fusion]\nae = "æː"\n',
    ],
)
def test_matches_tomllib_on_snippets(src):
    assert _minitoml.loads(src) == tomllib.loads(src)


def test_inventory_loads_with_fallback(monkeypatch):
    """予備パーサ経由でも Inventory が同じものを組み立てられる."""
    # 注意: konophon.inventory は同名の関数に隠されているので、
    # 属性経由ではなく sys.modules からモジュールを取る．
    inv_mod = sys.modules["konophon.inventory"]
    from konophon.inventory import Inventory

    real = Inventory.load()
    monkeypatch.setattr(inv_mod, "tomllib", _minitoml)
    fallback = Inventory.load()
    assert [p.spell for p in real] == [p.spell for p in fallback]
    assert real.legal_onset_pairs == fallback.legal_onset_pairs
    assert real.raw == fallback.raw
