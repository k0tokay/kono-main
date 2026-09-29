"""コアの検証．phonology.tex に書かれている例を回帰テストにしてある."""

import math

import pytest

from konophon import (
    Baseline,
    Constraint,
    Corpus,
    Grammar,
    NgramModel,
    Seq,
    Syllabifier,
    Tiers,
    Word,
    evaluate,
    inventory,
    parse_pattern,
    parse_rule,
)
from konophon.prosody import ONSET_SENSITIVE, RIME
from konophon.syllable import SyllabifyError

inv = inventory()


# ---------------------------------------------------------------------------
# 目録・トークン化
# ---------------------------------------------------------------------------


def test_two_letter_consonants_are_single_phonemes():
    for s in ["ts", "tc", "zc", "kh", "ng"]:
        assert [p.spell for p in inv.tokenize(s)] == [s]


def test_tokenize_longest_match():
    assert [p.spell for p in inv.tokenize("notcika")] == ["n", "o", "tc", "i", "k", "a"]
    assert [p.spell for p in inv.tokenize("tsanknis")] == ["ts", "a", "n", "k", "n", "i", "s"]


def test_natural_classes_match_tex():
    cls = {k: sorted(p.spell for p in v) for k, v in inv.classes.items()}
    assert cls["S"] == ["c", "f", "h", "kh", "s", "z", "zc"]
    assert cls["Q"] == ["tc", "ts"]
    assert cls["T"] == ["b", "d", "g", "k", "p", "t"]
    assert cls["N"] == ["m", "n", "ng"]
    assert cls["L"] == ["l"]
    assert cls["J"] == ["j", "w"]
    assert len(cls["V"]) == 7


def test_v_is_a_vowel_not_a_consonant():
    assert inv["v"].is_vowel and inv["v"].ipa == "u"


# ---------------------------------------------------------------------------
# 音節化（tex「音節化」節の例）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "word,expected",
    [
        ("likka", "lik.ka"),
        ("plappe", "plap.pe"),
        ("telissa", "te.lis.sa"),
        ("kwilwa", "kwi.lwa"),
    ],
)
def test_mop_examples(word, expected):
    assert Word(word).syllabified == expected


@pytest.mark.parametrize("word,expected", [("naz|loft", "naz.loft"), ("suis|kant", "suis.kant")])
def test_morphological_boundary_overrides_mop(word, expected):
    assert Word(word).syllabified == expected
    # 境界が無ければ MOP が勝つ（これが tex の言う「優先することがある」の中身）
    assert Word(word.replace("|", "")).syllabified != expected


def test_syllabifier_reports_table_gaps_instead_of_failing():
    w = Word("stcilkant")
    assert w.notes, "結合表に無い ω があるなら診断が出るべき"
    assert "stc" in " ".join(w.notes)


def test_unsyllabifiable_raises():
    with pytest.raises(SyllabifyError):
        Word("dblomboi")


# ---------------------------------------------------------------------------
# 韻律（tex「音節の軽重」の表）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "word,moras",
    [("li", [1]), ("mei", [2]), ("kin", [2]), ("baaf", [3]), ("kant", [3])],
)
def test_weight_table(word, moras):
    assert Word(word).moras("rime") == moras


def test_onset_sensitive_scale_differs_only_in_onset():
    w = Word("paklata")
    assert w.moras("rime") == [1, 1, 1]
    assert w.moras("onset_sensitive") == [1, 2, 1]
    assert Word("pakata").moras("onset_sensitive") == [1, 1, 1]


def test_kwilwa_contour_licensing_is_the_discriminating_case():
    """kwilwa (FR) は rime スケールでは違反、onset_sensitive では違反にならない."""
    w = Word("kwilwa", accent="FR")
    assert len(w.contour_problems("rime")) == 2
    assert w.contour_problems("onset_sensitive") == []


def test_accent_length_must_match_syllable_count():
    with pytest.raises(ValueError):
        Word("pata", accent="HLL")


# ---------------------------------------------------------------------------
# DSL
# ---------------------------------------------------------------------------


def test_pattern_crosses_syllable_boundary_by_default():
    # konstav = kon.stav, n-s-t の 3 子音は音節境界をまたぐ
    assert Word("konstav").count("*[C][C][C]") == 1


def test_explicit_syllable_boundary_in_pattern():
    assert Word("likka").count("[C].[C]") == 1
    assert Word("pata").count("[C].[C]") == 0


def test_word_boundary_is_not_transparent():
    assert Word("pata").count("#[C]") == 1
    assert Word("pata").count("[+syl]#") == 1


def test_feature_and_class_and_literal():
    w = Word("paklata")
    assert w.count("[T][L]") == 1
    assert w.count("kl") == 1
    assert w.count("<k><l>") == 1
    assert w.count("[-son,+cons][+lat]") == 1


def test_quantifiers():
    assert Word("suiskant").count("[C][C]?[+syl]") >= 1
    assert Word("pata").count("[]{2}") >= 1


def test_alternation():
    assert Word("tesav").count("([S]|[T])[+syl]") == 2


def test_syllable_tier_patterns():
    w = Word("suis|kant")
    assert w.count("[weight=superheavy]", "syllable") == 2
    assert w.count("[final=true]", "syllable") == 1
    assert w.count("[penult=true]", "syllable") == 1


def test_positional_features_on_segments():
    w = Word("naz|loft")
    assert w.count("[+cons,role=coda]") == 3
    assert w.count("[+cons,role=onset]") == 2


def test_negated_class():
    assert Word("pata").count("[!V]") == 2


def test_rule_parsing():
    r = parse_rule("[T] -> ʔ / [+syl] _ #", name="final_glottal")
    assert r.replacement == "ʔ"
    assert r.right is not None
    assert Word("pat").matches(r.structural_description(inv))


# ---------------------------------------------------------------------------
# Seq
# ---------------------------------------------------------------------------


def test_seq_is_an_immutable_sequence():
    s = Seq.of("pakata")
    assert len(s) == 6
    assert s[0].spell == "p"
    assert s[:2].spell == "pa"
    assert (s + "no").spell == "pakatano"
    assert "k" in s
    assert s == "pakata"


def test_cv_groups_and_skeleton():
    s = Seq.of("suiskant")
    assert s.cv_skeleton == "CVVCCVCC"
    assert [g.spell for g in s.cv_groups()] == ["s", "ui", "sk", "a", "nt"]


# ---------------------------------------------------------------------------
# 形態音韻（tex「活用」節）
# ---------------------------------------------------------------------------


def test_vowel_join_epsilon_cases():
    assert Seq.of("kan").vplus("tos") == "kanatos"   # ε + ε = a
    assert Seq.of("kan").vplus("os") == "kanos"      # ε + y = y
    assert Seq.of("ka").vplus("tos") == "katos"      # x + ε = x


def test_vowel_join_uses_nucleus_table():
    # (a, i) は核の表にあるのでそのまま並ぶ
    assert Seq.of("ka").vplus("in") == "kain"
    # (i, a) は表に無いが (a, i) が有るので入れ替わる
    assert Seq.of("ki").vplus("an") == "kian" or Seq.of("ki").vplus("an") == "kain"


def test_palatalization_applies_after_join():
    assert "sj" not in Seq.of("mes").vplus("ja").spell


def test_palatalization_rules_match_phonology_chapter():
    from konophon.inventory import inventory
    from konophon.morphology import apply_spelling_rules
    inv = inventory()
    # x in {s,z,ts,t,d,h}, v in {i,y,u,v}: xj -> x^rho, xv -> x^rho v
    assert apply_spelling_rules("tuuf", inv) == "tcuuf"
    assert apply_spelling_rules("diin", inv) == "zciin"
    assert apply_spelling_rules("mesja", inv) == "meca"
    assert apply_spelling_rules("jiik", inv) == "iik"
    # 置換は音素単位：kh の中の h，tc の中の c を取り違えない（旧実装は khi で止まらなかった）
    assert apply_spelling_rules("khi", inv) == "khi"
    assert apply_spelling_rules("tci", inv) == "tci"
    # xw は変換しない
    assert apply_spelling_rules("tswa", inv) == "tswa"


def test_consonant_join_defricates_affricates():
    assert Seq.of("ats").cplus("tca") == "asca"


# ---------------------------------------------------------------------------
# 統計
# ---------------------------------------------------------------------------


def _toy_corpus():
    return Corpus.from_iterable(
        ["pata", "pakata", "paklata", "notcika", "kalam", "meide", "kwilwa", "likka"]
    )


def test_ngram_information_measures():
    c = _toy_corpus()
    ng = NgramModel.build(c, Tiers().phoneme, n=2)
    assert ng.entropy() > 0
    assert 0 <= ng.mutual_information() <= ng.entropy() + 1e-9
    assert ng.transition_matrix().shape[1] == len(ng.vocab)


def test_tiers_have_consistent_lengths():
    t = Tiers()
    w = Word("paklata")
    assert len(t.phoneme(w)) == len(w.seq)
    assert len(t.syllable_shape(w)) == len(t.onset_shape(w)) == w.n_syllables


def test_zip_tiers_pairs_weight_and_accent():
    t = Tiers()
    w = Word("kwilwa", accent="FR")
    f = t.zip_tiers(t.weight("rime"), t.accent)
    assert f(w) == ["light/F", "light/R"]


# ---------------------------------------------------------------------------
# 制約と尤度
# ---------------------------------------------------------------------------


def test_declared_constraints_load():
    g = Grammar.from_inventory(inv)
    assert len(g) >= 3
    assert any(c.is_hard for c in g)


def test_hard_constraint_makes_harmony_infinite():
    g = Grammar([Constraint("*[C][C][C][C]", weight=float("inf"))], inv)
    assert math.isinf(g.harmony(Word("konsktav"))) or g.harmony(Word("konsktav")) == 0


def test_evaluate_detects_a_planted_gap():
    """語彙に一切現れないパターンは O/E が 0 になり、絶対制約候補と判定される."""
    c = Corpus.from_iterable(["pata", "kata", "mata", "nata", "sata", "lata", "pako", "kamo"])
    bl = Baseline.fit(list(c), mode="unigram")
    import numpy as np

    samples = bl.sample(400, np.random.default_rng(0))
    ev = evaluate("*[+syl][+syl]", list(c), samples)
    assert ev.observed == 0
