import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { execFile } from 'node:child_process';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, resolve } from 'node:path';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const execFileAsync = promisify(execFile);
const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const cliPath = resolve(projectRoot, 'bin/kono-dict.mjs');

function fixture() {
    const base = {
        translations: [],
        simple_translations: [],
        arguments: [],
        tags: [],
        contents: [],
        variations: [],
        relations: [],
        is_function: false,
    };
    return {
        words: [
            { ...base, id: 0, entry: '語彙', category: 'カテゴリ', upper_covers: [], lower_covers: [1] },
            { ...base, id: 1, entry: 'cat', category: '語彙', translations: ['猫'], upper_covers: [0], lower_covers: [] },
        ],
    };
}

const hash = text => createHash('sha256').update(text).digest('hex');

async function withTempDictionary(run) {
    const directory = await mkdtemp(resolve(tmpdir(), 'kono-dict-test-'));
    const dictionaryPath = resolve(directory, 'dictionary.json');
    const raw = `${JSON.stringify(fixture(), null, 2)}\n`;
    await writeFile(dictionaryPath, raw, 'utf8');
    try {
        await run({ directory, dictionaryPath, raw });
    } finally {
        await rm(directory, { recursive: true, force: true });
    }
}

test('CLI emits machine-readable search results without npm output', async () => {
    await withTempDictionary(async ({ dictionaryPath }) => {
        const { stdout, stderr } = await execFileAsync(process.execPath, [
            cliPath,
            'search',
            '--translation', '猫',
            '--dict', dictionaryPath,
        ]);
        assert.equal(stderr, '');
        const output = JSON.parse(stdout);
        assert.equal(output.ok, true);
        assert.equal(output.result.count, 1);
        assert.equal(output.result.results[0].id, 1);
    });
});

test('CLI requires a matching base hash for writes and persists an atomic patch', async () => {
    await withTempDictionary(async ({ directory, dictionaryPath, raw }) => {
        const patchPath = resolve(directory, 'patch.json');
        const patch = {
            version: 1,
            operations: [{
                op: 'set_fields',
                id: 1,
                expect: { entry: 'cat' },
                set: { translations: ['猫', 'ネコ'] },
            }],
        };
        await writeFile(patchPath, JSON.stringify(patch), 'utf8');

        await assert.rejects(
            execFileAsync(process.execPath, [cliPath, 'apply', patchPath, '--dict', dictionaryPath, '--write']),
            error => JSON.parse(error.stderr).error.code === 'MISSING_BASE_HASH',
        );

        patch.base_hash = hash(raw);
        await writeFile(patchPath, JSON.stringify(patch), 'utf8');
        const { stdout } = await execFileAsync(process.execPath, [
            cliPath,
            'apply', patchPath,
            '--dict', dictionaryPath,
            '--write',
        ]);
        const output = JSON.parse(stdout);
        assert.equal(output.result.written, true);
        const saved = JSON.parse(await readFile(dictionaryPath, 'utf8'));
        assert.deepEqual(saved.words[1].translations, ['猫', 'ネコ']);
        assert.deepEqual(saved.words[0].lower_covers, [1]);
    });
});
