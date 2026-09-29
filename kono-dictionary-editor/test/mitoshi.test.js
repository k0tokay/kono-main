import assert from 'node:assert/strict';
import test from 'node:test';
import { applyDictionaryPatch, validateDictionary } from '../src/domain/dictionaryCore.js';
import { sensesOf, virtualSenses } from '../src/domain/mitoshi.js';

function word(id, entry, category, upperCovers = [], lowerCovers = [], overrides = {}) {
    return {
        id, entry, category,
        translations: [], simple_translations: [],
        upper_covers: upperCovers, lower_covers: lowerCovers,
        arguments: [], tags: [], contents: [], variations: [], relations: [], is_function: false,
        ...overrides,
    };
}

// 語彙: 0 根 ─ 1 組織 ─ 2 会社, 3 学校；0 ─ 4 記述
// 見做し: 5 根 ─ 6 組織→記述（一様）, 7 組織→所在地（一様でない，to=4 を流用）
function fixture() {
    return {
        words: [
            word(0, '語彙', 'カテゴリ', [], [1, 4]),
            word(1, 'organization', '語彙', [0], [2, 3]),
            word(2, 'company', '語彙', [1], [], { translations: ['会社'] }),
            word(3, 'school', '語彙', [1], []),
            word(4, 'description', '語彙', [0], []),
            word(5, '見做し', 'カテゴリ', [], [6, 7]),
            word(6, '組織→構成する記述', '見做し', [5], [], { mitoshi_type: { from: 1, to: 4, relation: null, uniform: true } }),
            word(7, '組織→所在地', '見做し', [5], [], { mitoshi_type: { from: 1, to: 4, relation: null, uniform: false } }),
        ],
    };
}

test('uniform types apply to every proper descendant', () => {
    const { words } = fixture();
    assert.deepEqual(sensesOf(words, 2).map(s => s.type), [6]);
    assert.deepEqual(sensesOf(words, 1), []); // from 自身には当てない
    assert.equal(virtualSenses(words).length, 2);
    assert.equal(validateDictionary(fixture()).valid, true);
});

test('non-uniform types apply only where recorded, and exclude removes uniform ones', () => {
    const data = fixture();
    data.words[2].mitoshi_senses = [{ type: 7, target: null, exclude: false }, { type: 6, target: null, exclude: true }];
    assert.deepEqual(sensesOf(data.words, 2).map(s => s.type), [7]);
    assert.deepEqual(sensesOf(data.words, 3).map(s => s.type), [6]);
});

test('materialize creates a same-spelled word under the target node', () => {
    const result = applyDictionaryPatch(fixture(), { operations: [{ op: 'materialize_mitoshi', key: 'c', id: 2, type: 6 }] });
    const id = result.assignedIds.c;
    const created = result.data.words[id];
    assert.equal(created.entry, 'company');
    assert.deepEqual(created.upper_covers, [4]);
    assert.deepEqual(created.relations, [{ title: '組織→構成する記述', entry: 2 }]);
    assert.deepEqual(result.data.words[2].mitoshi_senses, [{ type: 6, target: id, exclude: false }]);
    assert.equal(sensesOf(result.data.words, 2)[0].target, id);
    assert.throws(
        () => applyDictionaryPatch(result.data, { operations: [{ op: 'materialize_mitoshi', id: 2, type: 6 }] }),
        error => error.code === 'MITOSHI_ALREADY_MATERIALIZED',
    );
});

test('a target outside the destination node is an error', () => {
    const data = fixture();
    data.words[2].mitoshi_senses = [{ type: 6, target: 3, exclude: false }];
    assert.ok(validateDictionary(data).errors.some(e => e.code === 'MITOSHI_TARGET_OUTSIDE'));
});

test('deleting a materialized target returns the sense to virtual', () => {
    const first = applyDictionaryPatch(fixture(), { operations: [{ op: 'materialize_mitoshi', key: 'c', id: 2, type: 6 }] });
    const id = first.assignedIds.c;
    const second = applyDictionaryPatch(first.data, {
        operations: [{ op: 'delete', id, expect: { entry: 'company' }, reconnect: 'none', reference_policy: 'remove' }],
    });
    assert.deepEqual(second.data.words[2].mitoshi_senses, [{ type: 6, target: null, exclude: false }]);
});
