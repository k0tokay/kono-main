#!/usr/bin/env node

import { createHash } from 'node:crypto';
import { readFile, rename, writeFile } from 'node:fs/promises';
import { basename, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
    DictionaryOperationError,
    analyzeForm,
    applyDictionaryPatch,
    dictionaryContext,
    dictionaryStats,
    patchSchema,
    resolveWordRef,
    searchDictionary,
    summarizeWord,
    validateDictionary,
} from '../src/domain/dictionaryCore.js';

const rootDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const defaultDictionaryPath = resolve(rootDir, 'src/data/konomeno-v5.json');
const booleanOptions = new Set(['pretty', 'write', 'exact']);

function parseArguments(argv) {
    const command = argv[0] || 'help';
    const options = {};
    const positionals = [];
    for (let index = 1; index < argv.length; index++) {
        const argument = argv[index];
        if (!argument.startsWith('--')) {
            positionals.push(argument);
            continue;
        }
        const key = argument.slice(2).replaceAll('-', '_');
        if (booleanOptions.has(key)) {
            options[key] = true;
            continue;
        }
        const value = argv[index + 1];
        if (value === undefined || value.startsWith('--')) {
            throw new DictionaryOperationError('MISSING_OPTION_VALUE', `--${argument.slice(2)} に値が必要です`);
        }
        options[key] = value;
        index++;
    }
    return { command, options, positionals };
}

function hashText(text) {
    return createHash('sha256').update(text).digest('hex');
}

function jsonText(value, pretty = false) {
    return `${JSON.stringify(value, null, pretty ? 2 : 0)}\n`;
}

async function loadDictionary(path) {
    let raw;
    try {
        raw = await readFile(path, 'utf8');
    } catch (error) {
        throw new DictionaryOperationError('READ_ERROR', `辞書を読み込めません: ${path}`, { cause: error.message });
    }
    try {
        return { data: JSON.parse(raw), raw, hash: hashText(raw) };
    } catch (error) {
        throw new DictionaryOperationError('INVALID_JSON', `辞書JSONを解析できません: ${path}`, { cause: error.message });
    }
}

async function readPatch(path) {
    let raw;
    try {
        if (path === '-') {
            const chunks = [];
            for await (const chunk of process.stdin) chunks.push(chunk);
            raw = Buffer.concat(chunks).toString('utf8');
        } else {
            raw = await readFile(resolve(path), 'utf8');
        }
    } catch (error) {
        throw new DictionaryOperationError('READ_ERROR', `パッチを読み込めません: ${path}`, { cause: error.message });
    }
    try {
        return JSON.parse(raw);
    } catch (error) {
        throw new DictionaryOperationError('INVALID_JSON', `パッチJSONを解析できません: ${path}`, { cause: error.message });
    }
}

async function atomicWrite(path, text) {
    const tempPath = resolve(dirname(path), `.${basename(path)}.${process.pid}.tmp`);
    await writeFile(tempPath, text, 'utf8');
    await rename(tempPath, path);
}

function requirePositional(positionals, index, label) {
    const value = positionals[index];
    if (value === undefined) throw new DictionaryOperationError('MISSING_ARGUMENT', `${label} が必要です`);
    return value;
}

function help() {
    return {
        usage: 'npm run dict -- <command> [arguments] [options]',
        commands: {
            search: 'search [query] [--entry text] [--translation text] [--category name] [--tag tag] [--exact] [--limit n] [--offset n]',
            show: 'show id:123 | entry:form',
            context: 'context id:123 | entry:form [--depth n] [--limit n]',
            form: 'form candidate [--limit n]',
            stats: 'stats',
            validate: 'validate',
            schema: 'schema',
            apply: 'apply patch.json | - [--write]',
        },
        global_options: {
            '--dict path': '辞書ファイルを明示する',
            '--pretty': 'JSONをインデントする',
        },
        references: '更新対象は必ず id:123 のような一意なIDで確認してください。entry: は重複時に失敗します。',
    };
}

async function main() {
    const parsed = parseArguments(process.argv.slice(2));
    const { command, options, positionals } = parsed;
    const pretty = options.pretty === true;

    if (command === 'help') {
        process.stdout.write(jsonText({ ok: true, command, result: help() }, pretty));
        return;
    }
    if (command === 'schema') {
        process.stdout.write(jsonText({ ok: true, command, result: patchSchema() }, pretty));
        return;
    }

    const dictionaryPath = resolve(options.dict || defaultDictionaryPath);
    const loaded = await loadDictionary(dictionaryPath);
    let result;

    if (command === 'stats') {
        result = dictionaryStats(loaded.data);
    } else if (command === 'search') {
        result = searchDictionary(loaded.data, {
            query: options.query || positionals[0],
            entry: options.entry,
            translation: options.translation,
            category: options.category,
            tag: options.tag,
            exact: options.exact,
            limit: options.limit,
            offset: options.offset,
        });
    } else if (command === 'show') {
        const ref = requirePositional(positionals, 0, 'id:123 または entry:form');
        result = summarizeWord(loaded.data, resolveWordRef(loaded.data, ref), { full: true });
    } else if (command === 'context') {
        const ref = requirePositional(positionals, 0, 'id:123 または entry:form');
        result = dictionaryContext(loaded.data, ref, { depth: options.depth, limit: options.limit });
    } else if (command === 'form') {
        const candidate = requirePositional(positionals, 0, '候補音列');
        result = analyzeForm(loaded.data, candidate, { limit: options.limit });
    } else if (command === 'validate') {
        result = validateDictionary(loaded.data);
        if (!result.valid) process.exitCode = 2;
    } else if (command === 'apply') {
        const patchPath = requirePositional(positionals, 0, 'パッチファイルパスまたは -');
        const patch = await readPatch(patchPath);
        if (patch.base_hash !== undefined && patch.base_hash !== loaded.hash) {
            throw new DictionaryOperationError('STALE_DICTIONARY', 'パッチの base_hash が現在の辞書と一致しません', {
                expected: patch.base_hash,
                actual: loaded.hash,
            });
        }
        const applied = applyDictionaryPatch(loaded.data, patch);
        const serialized = jsonText(applied.data, true);
        const nextHash = hashText(serialized);
        if (options.write) {
            if (typeof patch.base_hash !== 'string' || patch.base_hash.length === 0) {
                throw new DictionaryOperationError('MISSING_BASE_HASH', '--write にはパッチ内の base_hash が必要です', { current_hash: loaded.hash });
            }
            await atomicWrite(dictionaryPath, serialized);
        }
        result = {
            written: options.write === true,
            current_hash: loaded.hash,
            resulting_hash: nextHash,
            changes: applied.changes,
            assigned_ids: applied.assignedIds,
            removed_redundant_covers: applied.removedRedundantCovers,
            warnings: applied.validation.warnings,
        };
    } else {
        throw new DictionaryOperationError('UNKNOWN_COMMAND', `未知のコマンドです: ${command}`, { commands: Object.keys(help().commands) });
    }

    process.stdout.write(jsonText({
        ok: true,
        command,
        dictionary: dictionaryPath,
        hash: command === 'apply' && options.write ? result.resulting_hash : loaded.hash,
        result,
    }, pretty));
}

try {
    await main();
} catch (error) {
    const known = error instanceof DictionaryOperationError;
    process.stderr.write(jsonText({
        ok: false,
        error: {
            code: known ? error.code : 'INTERNAL_ERROR',
            message: error.message,
            details: known ? error.details : {},
        },
    }, process.argv.includes('--pretty')));
    process.exitCode = 1;
}
