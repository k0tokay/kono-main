import assert from 'node:assert/strict';
import test from 'node:test';
import { applyDictionaryPatch, summarizeWord, validateDictionary } from '../src/domain/dictionaryCore.js';

function word(id, entry, upperCovers = [], lowerCovers = [], overrides = {}) {
    return {
        id, entry,
        category: id === 0 ? 'カテゴリ' : '語彙',
        translations: [], simple_translations: [],
        upper_covers: upperCovers, lower_covers: lowerCovers,
        arguments: [], tags: [], contents: [], variations: [], relations: [], is_function: false,
        ...overrides,
    };
}

// 0 語彙 ─ 1 person ─ 2 teacher；0 ─ 3 teach（関係），4 teaching（ハブ），5 agent, 6 theme（射影），7 school
function fixture(axioms = []) {
    return {
        words: [
            word(0, '語彙', [], [1, 3, 4, 5, 6, 7]),
            word(1, 'person', [0], [2]),
            word(2, 'teacher', [1], [], { axioms }),
            word(3, 'teach', [0]),
            word(4, 'teaching', [0]),
            word(5, 'agent', [0]),
            word(6, 'theme', [0]),
            word(7, 'school', [0]),
        ],
    };
}

test('schema axioms validate and render', () => {
    const data = fixture([
        { kind: '定義', genus: 1, differentia: [{ relation: 3, value: 7 }] },
        { kind: '引き下げ', relation: 3, hub: 4, projections: [5, 6] },
    ]);
    const result = validateDictionary(data);
    assert.equal(result.valid, true, JSON.stringify(result.errors));
    const view = summarizeWord(data, data.words[2], { full: true }).axioms_view;
    assert.equal(view[0], '≡ person(1) ⊓ ∃teach(3).school(7)');
});

test('free formulas are outside the schema and warned', () => {
    const result = validateDictionary(fixture([{ kind: '式', text: 'teacher ⊓ student ⊑ ⊥', refs: [1] }]));
    assert.equal(result.valid, true);
    assert.ok(result.warnings.some(w => w.code === 'AXIOM_OUTSIDE_SCHEMA'));
});

test('malformed axioms and genus outside the ancestors are reported', () => {
    const bad = validateDictionary(fixture([{ kind: '引き下げ', relation: 3, hub: 4, projections: [5] }]));
    assert.ok(bad.errors.some(e => e.code === 'INVALID_AXIOM'));
    const genus = validateDictionary(fixture([{ kind: '定義', genus: 7, differentia: [{ relation: 3, value: 7 }] }]));
    assert.ok(genus.warnings.some(w => w.code === 'DEFINITION_GENUS_NOT_ANCESTOR'));
});

test('deleting a referenced word is rejected or prunes the axiom', () => {
    const data = fixture([{ kind: '引き下げ', relation: 3, hub: 4, projections: [5, 6] }]);
    assert.throws(
        () => applyDictionaryPatch(data, { operations: [{ op: 'delete', id: 5, expect: { entry: 'agent' }, reconnect: 'none', reference_policy: 'reject' }] }),
        error => error.code === 'WORD_IS_REFERENCED',
    );
    const removed = applyDictionaryPatch(data, { operations: [{ op: 'delete', id: 5, expect: { entry: 'agent' }, reconnect: 'none', reference_policy: 'remove' }] });
    assert.deepEqual(removed.data.words[2].axioms, []);
});
