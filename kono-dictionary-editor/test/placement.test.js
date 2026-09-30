import assert from 'node:assert/strict';
import test from 'node:test';
import { applyDictionaryPatch, validateDictionary } from '../src/domain/dictionaryCore.js';
import { assertedAncestors, childStateCounts, coverState, findDisjointnessViolations } from '../src/domain/placement.js';

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

// 0 語彙 ─ 1 animal（コンストラクタ分割 class）─ 2 mammal, 3 bird ─ 4 bat（mammal の下）
function fixture() {
    return {
        words: [
            word(0, '語彙', [], [1]),
            word(1, 'animal', [0], [2, 3], {
                partitions: [{ key: 'class', kind: 'コンストラクタ', exhaustive: false }],
            }),
            word(2, 'mammal', [1], [4], { cover_states: [{ parent: 1, state: '配置', partition: 'class' }] }),
            word(3, 'bird', [1], [], { cover_states: [{ parent: 1, state: '配置', partition: 'class' }] }),
            word(4, 'bat', [2], []),
        ],
    };
}

test('edges without a record are placed', () => {
    const data = fixture();
    assert.deepEqual(coverState(data.words[4], 2), { state: '配置', partition: null });
    assert.equal(validateDictionary(data).valid, true);
});

test('a patch putting a word under two disjoint branches is rejected', () => {
    assert.throws(
        () => applyDictionaryPatch(fixture(), { operations: [{ op: 'set_upper_covers', id: 4, from: [2], to: [2, 3] }] }),
        error => error.code === 'INTEGRITY_ERROR'
            && error.details.errors.some(e => e.code === 'DISJOINT_PARTITION_VIOLATION'),
    );
});

test('disjointness violation is detected and reported once at the lowest word', () => {
    const data = fixture();
    data.words[4].upper_covers = [2, 3];
    data.words[3].lower_covers = [4];
    const violations = findDisjointnessViolations(data.words);
    assert.equal(violations.length, 1);
    assert.equal(violations[0].id, 4);
    assert.deepEqual(violations[0].branches, [2, 3]);
});

test('placed edges outside any partition do not take part in disjointness', () => {
    const data = fixture();
    data.words[4].upper_covers = [2, 3];
    data.words[3].lower_covers = [4];
    data.words[3].cover_states = [];
    assert.equal(findDisjointnessViolations(data.words).length, 0);
    assert.equal(validateDictionary(data).valid, true);
});

test('partition on an upper-undecided edge and unknown partitions are errors', () => {
    const data = fixture();
    data.words[3].cover_states = [{ parent: 1, state: '上位未決', partition: 'class' }];
    assert.ok(validateDictionary(data).errors.some(e => e.code === 'PARTITION_ON_UNPLACED'));
    data.words[3].cover_states = [{ parent: 1, state: '配置', partition: 'nope' }];
    assert.ok(validateDictionary(data).errors.some(e => e.code === 'UNKNOWN_PARTITION'));
});

test('moving a word drops the state recorded for the old parent', () => {
    const result = applyDictionaryPatch(fixture(), {
        operations: [{ op: 'set_upper_covers', id: 3, from: [1], to: [0] }],
    });
    assert.deepEqual(result.data.words[3].cover_states, []);
    assert.ok(result.prunedCoverStates.includes(3));
});

test('child state counts', () => {
    const data = fixture();
    data.words[3].cover_states = [{ parent: 1, state: '上位未決', partition: null }];
    assert.deepEqual(childStateCounts(data.words, 1), { 配置: 1, 上位未決: 1 });
});

test('constructor partitions are always disjoint; feature partitions only when declared', () => {
    const data = fixture();
    data.words[4].upper_covers = [2, 3];
    data.words[3].lower_covers = [4];
    data.words[1].partitions = [{ key: 'class', kind: 'コンストラクタ', disjoint: false }];
    assert.equal(findDisjointnessViolations(data.words).length, 1);
    data.words[1].partitions = [{ key: 'class', kind: '素性', disjoint: false }];
    assert.equal(findDisjointnessViolations(data.words).length, 0);
    data.words[1].partitions = [{ key: 'class', kind: '素性', disjoint: true }];
    assert.equal(findDisjointnessViolations(data.words).length, 1);
});

test('upper-undecided edges assert no inclusion and are not traversed', () => {
    const data = fixture();
    // bat を bird の下へも置くが，上位未決（表示上の置き場）なので排他に反しない
    data.words[4].upper_covers = [2, 3];
    data.words[3].lower_covers = [4];
    data.words[4].cover_states = [{ parent: 3, state: '上位未決', partition: null }];
    assert.equal(findDisjointnessViolations(data.words).length, 0);
    assert.deepEqual([...assertedAncestors(data.words, 4)].sort(), [0, 1, 2]);
});
