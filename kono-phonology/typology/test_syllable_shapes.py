import unittest
from collections import Counter
from pathlib import Path
import sys
from syllable_shapes import prepare,syllabify
from syllable_typology import stats,js

class SyllableAnalysisTests(unittest.TestCase):
    def shapes(self,tokens,lang,onsets=()):
        seq,_=prepare(tokens.split(),lang)
        return [x[0] for x in syllabify(seq,lang,set(onsets))]
    def test_quantity_geminate_and_affricate(self):
        self.assertEqual(self.shapes('b o kː a','ita'),['CVC','CV'])
        self.assertEqual(self.shapes('tʃ aː','ita'),['CVV'])
        self.assertEqual(self.shapes('kː ɑ l ɑ','ekk'),['CV','CV'])
        self.assertEqual(self.shapes('kʲ j a k ɯ','jpn'),['CV','CV'])
        self.assertEqual(self.shapes('k i t̚ t e','jpn'),['CVC','CV'])
        self.assertEqual(self.shapes('mʲ i t̚ t s ɯ','jpn'),['CVC','CV'])
    def test_hiatus_and_mandarin_rime(self):
        self.assertEqual(self.shapes('k a o̞','jpn'),['CV','V'])
        self.assertEqual(self.shapes('t u o','cmn'),['CVV'])
        self.assertEqual(self.shapes('j ɛ n tɕ i ŋ','cmn'),['CVC','CVC'])
    def test_syllabic_r(self):
        self.assertEqual(self.shapes('b r d o','hrv'),['CV','CV'])
        self.assertEqual(self.shapes('t rː n','hrv'),['CVVC'])
    def test_russian_mongolian(self):
        self.assertEqual(self.shapes('g lˠ aˑ s','rus'),['CCVC'])
        self.assertEqual(self.shapes('x aːi r','khk'),['CVVC'])
    def test_kono_nasal_l_hard_restriction(self):
        project=Path(__file__).resolve().parent.parent
        sys.path.insert(0,str(project if (project/'konophon').exists() else Path('../kono-phonology').resolve()))
        from konophon import Word
        from konophon.syllable import SyllabifyError
        from syllable_typology import restricted_kono_word
        self.assertEqual([s.spell for s in restricted_kono_word(Word('fanlos')).syllables],['fan','los'])
        self.assertEqual([s.spell for s in restricted_kono_word(Word('somlai')).syllables],['som','lai'])
        # Even fallback must not silently reintroduce a forbidden initial onset.
        with self.assertRaises(SyllabifyError):restricted_kono_word(Word('nlelasa'))
    def test_unknown_not_silent_consonant(self):
        with self.assertRaises(ValueError):self.shapes('k @ a','ita')
        with self.assertRaises(ValueError):self.shapes('p t k','ita')
    def test_boundary_and_internal_sample_spaces(self):
        words=[['CV','CVC'],['CV'],['CVC','CV']]
        a=stats(words);b=stats(words,True)
        self.assertEqual(a['total'],2);self.assertEqual(b['total'],8)
        self.assertAlmostEqual(a['mi'],1.)
        self.assertAlmostEqual(js(Counter(CV=3),Counter(CVC=3)),1.)
        # Existing phoneme analysis uses the same boundary-inclusive joint marginals.
        project=Path(__file__).resolve().parent.parent
        if (project/'typology/analysis.py').exists():
            sys.path.insert(0,str(project/'typology'))
        else:sys.path.insert(0,'../kono-phonology/typology')
        from analysis import PhonemeStats
        ref=PhonemeStats('test',words)
        self.assertAlmostEqual(b['mi'],ref.mutual_information())
        self.assertAlmostEqual(b['h_cond'],ref.conditional_entropy())
if __name__=='__main__':unittest.main()
