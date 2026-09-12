"""IPA セグメント（NorthEuraLex の Segments 列）を粗い素性へ落とす.

コノメノとの比較用に，長さ・口蓋化・帯気などの二次的特徴を落とした
「広い」表記と，調音法クラス・有声性・C/V を返す．
"""
import unicodedata

MODIFIERS = set("ˑːʲˠʰʷ̥̊̃ˀ˞ˤ")  # 落とす修飾記号
VOWEL_BASES = set("aeiouyæøœɑɐɒɔəɘɛɜɞɤɨɪɯɵɶʉʊʌʏ")
NASAL = set("mnŋɲɳɴɱ")
LIQUID = set("lrɾɽɭʎʟɫɮɬʀʁ")
GLIDE = set("jwʋɥɰ")
PLOSIVE = set("pbtdkgqɢʔɖʈɟc")
AFFRICATE_PREFIX = ("ts", "dz", "tʃ", "dʒ", "tɕ", "dʑ", "tʂ", "dʐ", "pf")
VOICED_OBSTRUENT = set("bdgɢvzʒʑʐðɣʁɦɮ") 
FRICATIVE = set("fvszʃʒɕʑʂʐθðxɣχʁhɦçʝɸβɬɮ")


def strip_modifiers(seg: str) -> str:
    seg = unicodedata.normalize("NFD", seg)
    out = "".join(ch for ch in seg if ch not in MODIFIERS and unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", out)


def broad(seg: str) -> str:
    """修飾記号を落とした表記．二重母音は保持．"""
    s = strip_modifiers(seg)
    # 結合記号を落として空になったら元のまま
    return s or seg


def is_vowel(seg: str) -> bool:
    s = strip_modifiers(seg)
    return bool(s) and all(ch in VOWEL_BASES for ch in s)


def manner(seg: str) -> str:
    s = strip_modifiers(seg)
    if not s:
        return "?"
    if is_vowel(seg):
        return "vowel"
    if s.startswith(AFFRICATE_PREFIX) or (len(s) >= 2 and s[0] in "td" and s[1] in FRICATIVE):
        return "affricate"
    c = s[0]
    if c in NASAL:
        return "nasal"
    if c in LIQUID:
        return "liquid"
    if c in GLIDE:
        return "approximant"
    if c in PLOSIVE:
        return "plosive"
    if c in FRICATIVE:
        return "fricative"
    return "other"


def voiced(seg: str) -> bool | None:
    """阻害音についてのみ有声/無声を返す．共鳴音・母音は None."""
    m = manner(seg)
    if m not in ("plosive", "fricative", "affricate"):
        return None
    s = strip_modifiers(seg)
    return s[0] in VOICED_OBSTRUENT


def cv(seg: str) -> str:
    return "V" if is_vowel(seg) else "C"
