import unittest
from itertools import combinations, product
from appline_patterns import (Lexicon, TOP, _v_red, _atom_key, _candidate_patterns,
    _candidates_for_pattern, _h1_sort_ok, _h2_coargument_ok, _v_tau, charitable_interpretation)

def atom(rel, *args, transposed=False):
    return rel, tuple(args), transposed, (False,) * len(args)

def exhaustive_red(lex, atoms):
    keys = [_atom_key(a) for a in atoms]
    for size in range(len(keys) + 1):
        for selected in combinations(range(len(keys)), size):
            if all(any(lex.atom_entails(keys[j], goal) for j in selected) for goal in keys):
                return len(keys) - size

class RedundancyTests(unittest.TestCase):
    def setUp(self):
        self.lex = Lexicon()
        self.lex.add_concept('animal')
        self.lex.add_concept('cat', parents=('animal',))
        for rel in ('P', 'Q', 'S'):
            self.lex.add_relation(rel, ('animal', 'animal'))
        self.lex.add_implication('S', 'Q')
        self.lex.add_implication('Q', 'P')
        for name in ('a', 'b', 'c'):
            self.lex.add_individual(name, 'animal')

    def test_duplicate_and_transpose(self):
        self.assertEqual(_v_red([]), 0)
        self.assertEqual(_v_red([atom('P', 'a', 'b')] * 2), 1)
        self.assertEqual(_v_red([atom('P', 'a', 'b')] * 3), 2)
        self.assertEqual(_v_red([atom('P', 'a', 'b'), atom('P', 'b', 'a', transposed=True)]), 1)
        self.assertEqual(_v_red([atom('P', 'a', 'b'), atom('P', 'b', 'a')]), 0)

    def test_later_stronger_atom_and_cycles(self):
        atoms = [atom(r, 'a', 'b') for r in ('P', 'Q', 'S')]
        self.assertEqual(_v_red(atoms, self.lex), 2)
        self.assertEqual(_v_red(list(reversed(atoms)), self.lex), 2)
        self.lex.add_implication('P', 'S')
        self.assertEqual(_v_red(atoms, self.lex), 2)

    def test_sort_projection(self):
        self.lex.add_relation('animal', (TOP,))
        self.lex.add_relation('cat', (TOP,))
        self.assertEqual(_v_red([atom('cat', 'a'), atom('animal', 'a')], self.lex), 1)
        self.assertEqual(_v_red([atom('P', 'a', 'b'), atom('animal', 'a')], self.lex), 1)
        self.assertEqual(_v_red([atom('P', 'a', 'b'), atom('animal', 'c')], self.lex), 0)
        self.lex.add_relation('Other', ('animal', 'animal'))
        self.assertEqual(_v_red([atom('P', 'a', 'b'), atom('Other', 'a', 'b')], self.lex), 0)

    def test_matches_minimum_subset_definition(self):
        options = [atom(r, *args) for r in ('P', 'Q', 'S') for args in [('a','b'), ('b','a')]]
        for length in range(5):
            for atoms in product(options, repeat=length):
                self.assertEqual(_v_red(atoms, self.lex), exhaustive_red(self.lex, atoms))

    def test_pruned_search_matches_exhaustive_rank(self):
        for tokens in [('a','P','b','S','a'), ('a','P','S'), ('P','S'), ('Q','P','S')]:
            for delta in [('b',), ('a','b','c')]:
                all_v = []
                for pattern, index in _candidate_patterns(self.lex, tokens):
                    for atoms, tau, rec, _ in _candidates_for_pattern(self.lex, pattern, tokens, delta):
                        if _h1_sort_ok(self.lex, atoms) and _h2_coargument_ok(atoms):
                            all_v.append((exhaustive_red(self.lex, atoms), _v_tau(self.lex, atoms), rec, index, tau))
                best, _ = charitable_interpretation(self.lex, delta, tokens)
                self.assertEqual(best[0].v if best else None, min(all_v) if all_v else None)

    def test_general_arity(self):
        self.assertFalse(_h2_coargument_ok([('T', ('a','b','a'), False, (False,False,True))]))
        self.assertTrue(_h2_coargument_ok([atom('T','a','b','a')]))
        self.assertTrue(_h2_coargument_ok([('U',('a',),False,(True,))]))
        self.lex.add_relation('Unary', ('animal',))
        with self.assertRaises(ValueError):self.lex.add_implication('P', 'Unary')

if __name__ == '__main__':unittest.main()
