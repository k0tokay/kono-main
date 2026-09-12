"""コノメノ音素の共通定義とトークナイザ。

旧 kono-phonology（→ ref/ に退避済み）の Word/phono_sys への依存を切るための
自己完結モジュール。音素一覧は詳説2章 + gogaku/coining.tex の印象表に基づき、
旧 phono_sys.py に無かった ng を含む。

用法:
    from phonemes import tokenize, load_entries
"""

import json
import re
from pathlib import Path

KONO_BASE = Path(__file__).resolve().parent.parent

CONSONANTS = [
    "f", "s", "z", "c", "zc", "kh", "h",   # 摩擦音
    "ts", "tc",                            # 破擦音
    "p", "b", "t", "d", "k", "g",          # 破裂音
    "m", "n", "ng",                        # 鼻音
    "l",                                   # 流音
    "w", "j",                              # 半母音
]
VOWELS = ["a", "o", "e", "i", "u", "y", "v"]
PHONEMES = CONSONANTS + VOWELS

_LONGEST_FIRST = sorted(PHONEMES, key=len, reverse=True)


def tokenize(text):
    """綴りを最長一致で音素列に分解する。分解できない場合は None。"""
    ans = []
    i = 0
    while i < len(text):
        for p in _LONGEST_FIRST:
            if text.startswith(p, i):
                ans.append(p)
                i += len(p)
                break
        else:
            return None
    return ans


# ---- 辞書ローダー ----

V5_PATH = KONO_BASE / "kono-dictionary-editor" / "src" / "data" / "konomeno-v5.json"
SAIMENO_PATH = KONO_BASE / "ref" / "kono-phonology" / "dict" / "saimeno-v4.json"


def load_v5_entries(path=V5_PATH, root="語彙"):
    """v5 辞書（正典）からラテン文字の見出し語を返す。

    トップレベルは「語彙」「冠詞」「音列」「慣用表現」「括弧」に分かれており、
    既定では「語彙」サブツリーのみを対象とする（root=None で全件）。
    """
    words = [w for w in json.load(open(path))["words"] if w]
    if root is not None:
        byid = {w["id"]: w for w in words}
        keep = set()
        stack = [w["id"] for w in words if w["entry"] == root and not w.get("upper_covers")]
        while stack:
            i = stack.pop()
            if i in keep:
                continue
            keep.add(i)
            stack.extend(byid[i].get("lower_covers", []))
        words = [byid[i] for i in keep]
    return sorted({w["entry"] for w in words
                   if w.get("entry") and re.fullmatch(r"[a-z]+", w["entry"])})


def load_zpdic_entries(path):
    """zpdic 形式（saimeno-v4.json / konomeno-v5-zpdic.json）から見出し語を返す。"""
    words = json.load(open(path))["words"]
    return [w["entry"]["form"] for w in words
            if w and re.fullmatch(r"[a-z]+", w["entry"]["form"])]
