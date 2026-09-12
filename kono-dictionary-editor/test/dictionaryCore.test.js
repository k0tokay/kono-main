import assert from 'node:assert/strict';
import test from 'node:test';
import {
    DictionaryOperationError,
    applyDictionaryPatch,
    resolveWordRef,
    searchDictionary,
    validateDictionary,
} from '../src/domain/dictionaryCore.js';

function word(id, entry, upperCovers = [], lowerCovers = [], overrides = {}) {
    return {
        id,
        entry,
        translations: [],
        simple_translations: [],
        category: id === 0 ? 'カテゴリ' : '語彙',
        upper_covers: upperCovers,
        lower_covers: lowerCovers,
        arguments: [],
        tags: [],
        contents: [],
        variations: [],
        relations: [],
        is_function: false,
        ...overrides,
    };
}

function fixture() {
    return {
        words: [
            word(0, '語彙', [], [1]),
            word(1, 'animal', [0], [2], { translations: ['動物'] }),
            word(2, 'cat', [1], [], { translations: ['猫'] }),
        ],
    };
}

test('validates a consistent Hasse DAG', () => {
    const validation = validateDictionary(fixture());
    assert.equal(validation.valid, true);
    assert.deepEqual(validation.errors, []);
});

test('detects an asymmetric cover without mutating the dictionary', () => {
    const data = fixture();
    data.words[0].lower_covers = [];
    const validation = validateDictionary(data);
    assert.equal(validation.valid, false);
    assert.equal(validation.errors[0].code, 'ASYMMETRIC_COVER');
    assert.deepEqual(data.words[0].lower_covers, []);
});

test('patch application does not guess how to repair an unrelated asymmetric cover', () => {
    const data = fixture();
    data.words[0].lower_covers = [];
    assert.throws(
        () => applyDictionaryPatch(data, { version: 1, operations: [] }),
        error => error instanceof DictionaryOperationError
            && error.code === 'INTEGRITY_ERROR'
            && error.details.errors.some(issue => issue.code === 'ASYMMETRIC_COVER'),
    );
    assert.deepEqual(data.words[0].lower_covers, []);
});

test('set_upper_covers updates reverse links from a single structural input', () => {
    const applied = applyDictionaryPatch(fixture(), {
        version: 1,
        operations: [{ op: 'set_upper_covers', id: 2, from: [1], to: [0] }],
    });
    assert.deepEqual(applied.data.words[2].upper_covers, [0]);
    assert.deepEqual(applied.data.words[0].lower_covers, [1, 2]);
    assert.deepEqual(applied.data.words[1].lower_covers, []);
    assert.equal(applied.validation.valid, true);
});

test('set_upper_covers rejects a stale from precondition', () => {
    assert.throws(
        () => applyDictionaryPatch(fixture(), {
            operations: [{ op: 'set_upper_covers', id: 2, from: [0], to: [1] }],
        }),
        error => error instanceof DictionaryOperationError && error.code === 'PRECONDITION_FAILED',
    );
});

test('a patch that creates a cycle is rejected before persistence', () => {
    assert.throws(
        () => applyDictionaryPatch(fixture(), {
            operations: [{ op: 'set_upper_covers', id: 1, from: [0], to: [2] }],
        }),
        error => error instanceof DictionaryOperationError
            && error.code === 'INTEGRITY_ERROR'
            && error.details.errors.some(issue => issue.code === 'CYCLE'),
    );
});

test('redundant parent links are transitively reduced and reported', () => {
    const applied = applyDictionaryPatch(fixture(), {
        operations: [{ op: 'set_upper_covers', id: 2, from: [1], to: [0, 1] }],
    });
    assert.deepEqual(applied.data.words[2].upper_covers, [1]);
    assert.deepEqual(applied.removedRedundantCovers, [{ parent: 0, child: 2 }]);
});

test('add assigns the next sparse-array ID and maintains reverse covers', () => {
    const data = fixture();
    data.words.splice(2, 0, null);
    data.words[3] = { ...data.words[3], id: 3 };
    data.words[1].lower_covers = [3];
    const applied = applyDictionaryPatch(data, {
        operations: [{
            op: 'add',
            key: 'dog',
            upper_covers: [1],
            word: { entry: 'dog', translations: ['犬'], arguments: [4] },
        }],
    });
    assert.equal(applied.assignedIds.dog, 4);
    assert.equal(applied.data.words[2], null);
    assert.deepEqual(applied.data.words[4].arguments, [4]);
    assert.ok(applied.data.words[1].lower_covers.includes(4));
});

test('set_fields cannot modify structural fields', () => {
    assert.throws(
        () => applyDictionaryPatch(fixture(), {
            operations: [{ op: 'set_fields', id: 2, set: { lower_covers: [] } }],
        }),
        error => error instanceof DictionaryOperationError && error.code === 'STRUCTURAL_FIELD',
    );
});

test('new dangling argument references are rejected even though legacy ones are warnings', () => {
    assert.throws(
        () => applyDictionaryPatch(fixture(), {
            operations: [{ op: 'set_fields', id: 2, set: { arguments: [999] } }],
        }),
        error => error instanceof DictionaryOperationError && error.code === 'UNKNOWN_ID',
    );
});

test('entry references fail rather than selecting arbitrarily when duplicated', () => {
    const data = fixture();
    data.words.push(word(3, 'cat', [1], []));
    data.words[1].lower_covers.push(3);
    assert.throws(
        () => resolveWordRef(data, 'entry:cat'),
        error => error instanceof DictionaryOperationError && error.code === 'AMBIGUOUS_ENTRY',
    );
});

test('validation warns about duplicate entries within one category', () => {
    const data = fixture();
    data.words.push(word(3, 'cat', [1], []));
    data.words[1].lower_covers.push(3);
    const validation = validateDictionary(data);
    assert.equal(validation.valid, true);
    assert.deepEqual(
        validation.warnings.find(issue => issue.code === 'DUPLICATE_ENTRY_IN_CATEGORY')?.ids,
        [2, 3],
    );
});

test('delete explicitly resolves a partially detached word without resurrecting it', () => {
    const data = fixture();
    data.words[1].lower_covers = [];
    const applied = applyDictionaryPatch(data, {
        operations: [{
            op: 'delete',
            id: 2,
            expect: { entry: 'cat' },
            reconnect: 'none',
            reference_policy: 'reject',
        }],
    });
    assert.equal(applied.data.words[2], null);
    assert.deepEqual(applied.data.words[1].lower_covers, []);
    assert.equal(applied.validation.valid, true);
    assert.equal(applied.changes.find(change => change.id === 2)?.type, 'delete');
});

test('delete rejects semantic references unless their removal is explicit', () => {
    const data = fixture();
    data.words[1].arguments = [2];
    data.words[1].relations = [{ title: 'related', entry: 2 }];
    const operation = {
        op: 'delete',
        id: 2,
        expect: { entry: 'cat' },
        reconnect: 'none',
        reference_policy: 'reject',
    };
    assert.throws(
        () => applyDictionaryPatch(data, { operations: [operation] }),
        error => error instanceof DictionaryOperationError && error.code === 'WORD_IS_REFERENCED',
    );

    operation.reference_policy = 'remove';
    const applied = applyDictionaryPatch(data, { operations: [operation] });
    assert.deepEqual(applied.data.words[1].arguments, []);
    assert.deepEqual(applied.data.words[1].relations, []);
    assert.equal(applied.validation.valid, true);
});

test('delete reconnects children to parents only when requested', () => {
    const data = fixture();
    data.words.push(word(3, 'kitten', [2], []));
    data.words[2].lower_covers = [3];
    const applied = applyDictionaryPatch(data, {
        operations: [{
            op: 'delete',
            id: 2,
            expect: { entry: 'cat' },
            reconnect: 'parents',
            reference_policy: 'reject',
        }],
    });
    assert.deepEqual(applied.data.words[3].upper_covers, [1]);
    assert.deepEqual(applied.data.words[1].lower_covers, [3]);
    assert.equal(applied.validation.valid, true);
});

test('search reports truncation instead of implying the result is complete', () => {
    const data = fixture();
    data.words[1].translations = ['生物'];
    data.words[2].translations = ['生物'];
    const result = searchDictionary(data, { translation: '生物', limit: 1 });
    assert.equal(result.count, 2);
    assert.equal(result.results.length, 1);
    assert.equal(result.truncated, true);
});
