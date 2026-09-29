import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { applyDictionaryPatch, analyzeForm, validateDictionary } from '../src/domain/dictionaryCore.js';
import {
    PHONEME_SPELLINGS,
    deriveSequenceCovers,
    isPhonemePrefix,
    tokenizePhonemes,
} from '../src/domain/soundSequences.js';

function word(id, entry, category, upperCovers = [], lowerCovers = []) {
    return {
        id, entry, category,
        translations: [], simple_translations: [],
        upper_covers: upperCovers, lower_covers: lowerCovers,
        arguments: [], tags: [], contents: [], variations: [], relations: [], is_function: false,
    };
}

// 0: 音列の根，1: a，2: t，3: tc，4: ta，5: sta（被覆は接頭辞順序の導出どおり）
function fixture() {
    return {
        words: [
            word(0, '音列', 'カテゴリ', [], [1, 2, 3, 5]),
            word(1, 'a', '音列', [0], []),
            word(2, 't', '音列', [0], [4]),
            word(3, 'tc', '音列', [0], []),
            word(4, 'ta', '音列', [2], []),
            word(5, 'sta', '音列', [0], []),
        ],
    };
}

test('phoneme spellings match phonology.toml', () => {
    const toml = readFileSync(new URL('../../kono-phonology/konophon/data/phonology.toml', import.meta.url), 'utf8');
    const spells = [...toml.matchAll(/^spell = "([^"]+)"/gm)].map(m => m[1]);
    assert.deepEqual([...spells].sort(), [...PHONEME_SPELLINGS].sort());
});

test('tokenizes by longest match', () => {
    assert.deepEqual(tokenizePhonemes('tcilk'), ['tc', 'i', 'l', 'k']);
    assert.deepEqual(tokenizePhonemes('ngolmi'), ['ng', 'o', 'l', 'm', 'i']);
    assert.equal(tokenizePhonemes('kstra'), null);
});

test('order is phoneme prefix, not substring', () => {
    assert.equal(isPhonemePrefix(tokenizePhonemes('t'), tokenizePhonemes('tca')), false); // tc は一音素
    assert.equal(isPhonemePrefix(tokenizePhonemes('ta'), tokenizePhonemes('tak')), true);
    assert.equal(isPhonemePrefix(tokenizePhonemes('ta'), tokenizePhonemes('sta')), false); // 部分文字列だが接頭辞でない
});

test('derived covers are the Hasse diagram of the prefix order', () => {
    const { covers } = deriveSequenceCovers(fixture().words);
    assert.deepEqual(covers.get(4), [2]); // ta の上位は t だけ（a は接頭辞でない）
    assert.deepEqual(covers.get(5), [0]); // sta：s は未登録なので根
    assert.deepEqual(covers.get(3), [0]); // tc は t で始まらない（一音素）
    assert.equal(validateDictionary(fixture()).valid, true);
});

test('validator reports covers that differ from derivation', () => {
    const data = fixture();
    data.words[4].upper_covers = [0];
    data.words[2].lower_covers = [];
    data.words[0].lower_covers.push(4);
    const result = validateDictionary(data);
    assert.ok(result.errors.some(e => e.code === 'SEQUENCE_COVER_MISMATCH' && e.id === 4));
});

test('adding a sequence re-derives covers of others', () => {
    const result = applyDictionaryPatch(fixture(), {
        operations: [{ op: 'add', word: { entry: 'st', category: '音列' } }],
    });
    const words = result.data.words;
    assert.deepEqual(words[6].upper_covers, [0]); // st：s は未登録なので根
    assert.deepEqual(words[5].upper_covers, [6]); // sta は st の下へ
    assert.ok(result.derivedSequenceCovers.includes(5));
});

test('set_upper_covers on a sequence is rejected', () => {
    assert.throws(
        () => applyDictionaryPatch(fixture(), { operations: [{ op: 'set_upper_covers', id: 4, from: [2], to: [0] }] }),
        error => error.code === 'SEQUENCE_COVERS_DERIVED',
    );
});

test('analyzeForm does not match sequences across phoneme boundaries', () => {
    const data = fixture();
    const result = analyzeForm(data, 'tcata');
    const found = Object.fromEntries(result.registered_sequences.map(s => [s.entry, s.positions]));
    assert.deepEqual(found.tc, [0]);
    assert.deepEqual(found.ta, [3]);
    assert.deepEqual(found.t, [3]);
});
