"""konophon — コノメノ音韻論の分析ライブラリ.

    >>> from konophon import Word, inventory
    >>> w = Word("paklata", accent="LFL")
    >>> w.syllabified
    'pa.kla.ta'
    >>> w.moras("rime"), w.moras("onset_sensitive")
    ([1, 1, 1], [1, 2, 1])
    >>> w.contour_problems("rime")
    ['σ2 (kla) は F を担うが rime=1μ < 2μ']

主要な入口:

``inventory()``       音素目録（phonology.toml が唯一の定義元）
``Seq``               音素列の代数
``Word``              音節化・アクセント込みの分析単位
``parse_pattern``     素性列 DSL
``Grammar`` ``evaluate``  制約の尤度評価
``Tiers`` ``NgramModel``  遷移行列・エントロピー・PMI
``Corpus``            辞書の読み込み
"""

from .constraints import Baseline, Constraint, Evaluation, Grammar, evaluate, evaluate_many
from .corpus import Corpus, autoload, load_accent_tsv, load_v5, load_wordlist, load_zpdic
from .dsl import Pattern, Rule, parse_pattern, parse_rule, parse_segment_spec
from .inventory import Inventory, Phoneme, inventory
from .morphology import consonant_join, vowel_join
from .prosody import ONSET_SENSITIVE, RIME, AccentPattern, WeightScale, get_scale
from .seq import Seq
from .stats import NgramModel, Tiers, chi2_independence, cooccurrence, positional_distribution, tier_distribution
from .syllable import Syllabifier, Syllable, SyllabifyError
from .word import Word

__version__ = "0.1.0"

__all__ = [
    "AccentPattern",
    "Baseline",
    "Constraint",
    "Corpus",
    "Evaluation",
    "Grammar",
    "Inventory",
    "NgramModel",
    "ONSET_SENSITIVE",
    "Pattern",
    "Phoneme",
    "RIME",
    "Rule",
    "Seq",
    "Syllabifier",
    "Syllable",
    "SyllabifyError",
    "Tiers",
    "WeightScale",
    "Word",
    "autoload",
    "chi2_independence",
    "consonant_join",
    "cooccurrence",
    "evaluate",
    "evaluate_many",
    "get_scale",
    "inventory",
    "load_accent_tsv",
    "load_v5",
    "load_wordlist",
    "load_zpdic",
    "parse_pattern",
    "parse_rule",
    "parse_segment_spec",
    "positional_distribution",
    "tier_distribution",
    "vowel_join",
]
