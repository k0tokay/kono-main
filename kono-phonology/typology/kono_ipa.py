"""
コノメノ綴り音素列 → IPA 変換

main-detail.tex の音素一覧 + gogaku.tex の母音融合規則に基づく。
Word クラスの出力（綴りベースの音素リスト）を受け取り、
IPA音素リストに変換する。
"""

# --- 子音: 綴り → IPA ---
CONSONANT_IPA = {
    "f": "f",
    "s": "s",
    "z": "z",
    "c": "ʃ",
    "zc": "ʒ",
    "kh": "x",
    "h": "h",
    "ts": "t͡s",
    "tc": "t͡ʃ",
    "p": "p",
    "b": "b",
    "t": "t",
    "d": "d",
    "k": "k",
    "g": "g",
    "m": "m",
    "n": "n",
    "ng": "ŋ",
    "l": "l",
    "w": "w",
    "j": "j",
}

# --- 単母音: 綴り → IPA ---
VOWEL_IPA = {
    "a": "a",
    "o": "o",
    "e": "e",
    "i": "i",
    "y": "y",
    "u": "ɘ",
    "v": "u",
}

VOWELS = set(VOWEL_IPA.keys())

# --- 母音連続の融合規則 (gogaku.tex) ---
# 融合: 2母音 → 1つの長母音
VOWEL_FUSION = {
    ("a", "e"): ["æː"],
    ("e", "a"): ["æː"],
    ("o", "e"): ["œː"],
    ("o", "y"): ["øː"],
    # 同母音の長母音化
    ("a", "a"): ["aː"],
    ("o", "o"): ["oː"],
    ("e", "e"): ["eː"],
    ("i", "i"): ["iː"],
    ("y", "y"): ["yː"],
    ("u", "u"): ["ɘː"],
    ("v", "v"): ["uː"],
}

# v-attraction: v に引っ張られるパターン
V_ATTRACTION = {
    ("a", "v"): ["ɔː"],
    ("o", "v"): ["oː"],
}

# 透明 (そのまま2音素): ai, ay, au, oi, ou, ei, ey, ui, uy
# これらは個別にIPA変換するだけ


def spelling_to_ipa(ph_list: list[str]) -> list[str]:
    """綴り音素リスト → IPA音素リスト"""
    result = []
    i = 0
    while i < len(ph_list):
        ph = ph_list[i]

        if ph in VOWELS and i + 1 < len(ph_list) and ph_list[i + 1] in VOWELS:
            pair = (ph, ph_list[i + 1])

            if pair in V_ATTRACTION:
                result.extend(V_ATTRACTION[pair])
                i += 2
                continue

            if pair in VOWEL_FUSION:
                result.extend(VOWEL_FUSION[pair])
                i += 2
                continue

            # 透明なペア: 個別にIPA変換
            result.append(VOWEL_IPA[ph])
            i += 1
            continue

        if ph in VOWEL_IPA:
            result.append(VOWEL_IPA[ph])
        elif ph in CONSONANT_IPA:
            result.append(CONSONANT_IPA[ph])
        else:
            result.append(ph)
        i += 1

    return result
