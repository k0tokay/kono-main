import assert from 'node:assert/strict';
import test from 'node:test';
import { applyDictionaryPatch, summarizeWord, validateDictionary } from '../src/domain/dictionaryCore.js';

function word(id, entry, upperCovers = [], lowerCovers = [], overrides = {}) {
    return {
        id, entry,
        category: id === 0 ? 'カテゴリ' : '語彙',
        translations: [], simple_translations: [],
        upper_covers: upperCovers, lower_covers: lowerCovers,
        arguments: [id], tags: [], contents: [], variations: [], relations: [], is_function: false,
        ...overrides,
    };
}

// 0 語彙 ─ 1 家，2 領域，3 所在（関係 x1=家, x2=領域）
function fixture(metaProps) {
    return {
        words: [
            word(0, '語彙', [], [1, 2, 3]),
            word(1, 'ie', [0]),
            word(2, 'ryoiki', [0]),
            word(3, 'shozai', [0], [], { arguments: [1, 2], ...(metaProps ? { meta_props: metaProps } : {}) }),
        ],
    };
}

test('meta properties on a relation validate and render', () => {
    const data = fixture({ functional: [1], total_on: [{ node: 1, arg: 1 }], elidable: [1] });
    const result = validateDictionary(data);
    assert.equal(result.valid, true, JSON.stringify(result.errors));
    assert.equal(result.warnings.some(w => w.code === 'ELIDABLE_NOT_DETERMINED'), false);
    assert.equal(
        summarizeWord(data, data.words[3], { full: true }).meta_props_view,
        'x1 から関数的・ie(1) 上で x1 から全域的・x1 から省略可（見做し）',
    );
});

test('elision without functionality or totality in that direction is warned', () => {
    const result = validateDictionary(fixture({ elidable: [2] }));
    assert.equal(result.valid, true);
    assert.ok(result.warnings.some(w => w.code === 'ELIDABLE_NOT_DETERMINED' && w.arg === 2));
});

test('meta properties belong to binary relation words only', () => {
    const data = fixture();
    data.words[1].meta_props = { symmetric: true };
    assert.ok(validateDictionary(data).errors.some(e => e.code === 'META_PROPS_ON_NON_RELATION'));
    const bad = fixture({ functional: [3] });
    assert.ok(validateDictionary(bad).errors.some(e => e.code === 'INVALID_META_PROPS'));
});

test('a node used in total_on cannot be deleted under the reject policy', () => {
    const data = fixture({ total_on: [{ node: 1, arg: 1 }] });
    assert.throws(
        () => applyDictionaryPatch(data, { operations: [{ op: 'delete', id: 1, expect: { entry: 'ie' }, reconnect: 'none', reference_policy: 'reject' }] }),
        error => error.code === 'WORD_IS_REFERENCED',
    );
});
