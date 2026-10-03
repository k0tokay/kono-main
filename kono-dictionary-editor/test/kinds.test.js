import assert from 'node:assert/strict';
import test from 'node:test';
import { applyDictionaryPatch, validateDictionary } from '../src/domain/dictionaryCore.js';
import { kindsOf, membersOf, signatureOf } from '../src/domain/kinds.js';

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

// 0 根 ─ 1 konofon（1項述語を生成），2 flentos（属性のない種），3 coto（1項述語），4 to（2項関係），
//        5 konomili（定数を生成），6 komatci（定数．小町は人）
function fixture() {
    return {
        words: [
            word(0, 'root', [], [1, 2, 3, 4, 5, 6], { arguments: [], is_function: null }),
            word(1, 'konofon', [0], [], { arguments: [], is_function: null, generator: { tArity: 1, isFunc: false } }),
            word(2, 'flentos', [0], [], { arguments: [], is_function: null }),
            word(3, 'coto', [0]),
            word(4, 'to', [0], [], { arguments: [3, 3], dent: [2] }),
            word(5, 'konomili', [0], [], { arguments: [], is_function: null, generator: { tArity: 1, isFunc: true } }),
            word(6, 'komatci', [0], [], { arguments: [3], is_function: true, dent: [3] }),
        ],
    };
}

test('signatures with unset is_function or a function of arity -1 are unknown', () => {
    assert.equal(signatureOf({ arguments: [], is_function: null }), null);
    assert.equal(signatureOf({ arguments: [], is_function: true }), null);
    assert.deepEqual(signatureOf({ arguments: [], is_function: false }), { tArity: 0, isFunc: false });
});

test('members come from the signature and from dent; a constant contributes its value', () => {
    const data = fixture();
    assert.equal(validateDictionary(data).valid, true, JSON.stringify(validateDictionary(data).errors));
    assert.deepEqual(membersOf(data.words, 1).map(m => [m.id, m.show, m.source]), [[3, 'quote', 'signature']]);
    assert.deepEqual(membersOf(data.words, 2).map(m => [m.id, m.show, m.source]), [[4, 'quote', 'fact']]);
    assert.deepEqual(membersOf(data.words, 3).map(m => [m.id, m.show]), [[6, 'word']]);
    assert.deepEqual(membersOf(data.words, 5).map(m => [m.id, m.show]), [[6, 'quote']]);
    assert.deepEqual(kindsOf(data.words, 3).map(k => k.kind), [1]);
});

test('materializing makes one constant per sense, without covers, and moves dent', () => {
    const result = applyDictionaryPatch(fixture(), { operations: [{ op: 'materialize_quote', key: 'q', id: 4 }] });
    const id = result.assignedIds.q;
    const q = result.data.words[id];
    assert.equal(q.entry, '⌜to⌝');
    assert.equal(q.quote_of, 4);
    assert.deepEqual(q.upper_covers, []);
    assert.deepEqual(q.dent, [2]);
    assert.equal(result.data.words[4].dent, undefined);
    assert.deepEqual(membersOf(result.data.words, 2).map(m => [m.id, m.show]), [[id, 'word']]);
    assert.ok(membersOf(result.data.words, 5).some(m => m.id === id), 'the new constant is itself generated under konomili');
    assert.throws(
        () => applyDictionaryPatch(result.data, { operations: [{ op: 'materialize_quote', id: 4 }] }),
        error => error.code === 'QUOTE_ALREADY_MATERIALIZED',
    );
});

test('a dent fact that the signature already gives is warned', () => {
    const data = fixture();
    data.words[3].dent = [1];
    assert.ok(validateDictionary(data).warnings.some(w => w.code === 'DENT_ALREADY_GENERATED'));
});
