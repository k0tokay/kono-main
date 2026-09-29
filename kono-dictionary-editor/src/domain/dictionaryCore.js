import { pruneCoverStates, validatePlacement } from './placement.js';
import { materializeMitoshiInPlace, pruneMitoshi, sensesOf, validateMitoshi } from './mitoshi.js';
import { applyDerivedSequenceCovers, isSequenceWord, sequenceCoverMismatches, tokenizePhonemes } from './soundSequences.js';

export const EDITABLE_FIELDS = new Set([
    'entry',
    'translations',
    'simple_translations',
    'arguments',
    'tags',
    'contents',
    'variations',
    'relations',
    'is_function',
    'partitions',
    'cover_states',
    'mitoshi_type',
    'mitoshi_senses',
]);

export class DictionaryOperationError extends Error {
    constructor(code, message, details = {}) {
        super(message);
        this.name = 'DictionaryOperationError';
        this.code = code;
        this.details = details;
    }
}

const asArray = value => Array.isArray(value) ? value : [];
const isPlainObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const unique = values => [...new Set(values)];
const sameSet = (left, right) => {
    const a = unique(left).sort((x, y) => x - y);
    const b = unique(right).sort((x, y) => x - y);
    return a.length === b.length && a.every((value, index) => value === b[index]);
};

function liveWord(words, id) {
    return Number.isInteger(id) && id >= 0 && id < words.length && words[id] !== null;
}

function wordLabel(words, id) {
    const word = words[id];
    return word ? { id, entry: word.entry, translations: asArray(word.translations).slice(0, 3) } : { id, missing: true };
}

function requireDictionary(data) {
    if (!isPlainObject(data) || !Array.isArray(data.words)) {
        throw new DictionaryOperationError('INVALID_DICTIONARY', '辞書は words 配列を持つオブジェクトでなければなりません');
    }
    return data.words;
}

function requireLiveId(words, id, field = 'id') {
    if (!liveWord(words, id)) {
        throw new DictionaryOperationError('UNKNOWN_ID', `${field} が実在する単語を参照していません: ${id}`, { field, id });
    }
}

function requireIdArray(words, values, field, { allowDuplicates = false } = {}) {
    if (!Array.isArray(values)) {
        throw new DictionaryOperationError('INVALID_FIELD', `${field} はIDの配列でなければなりません`, { field });
    }
    if (!allowDuplicates && unique(values).length !== values.length) {
        throw new DictionaryOperationError('DUPLICATE_REFERENCE', `${field} に重複したIDがあります`, { field, values });
    }
    for (const id of values) requireLiveId(words, id, field);
}

function adjacencyFromUpper(words) {
    const adjacency = Array.from({ length: words.length }, () => []);
    for (const word of words) {
        if (!word) continue;
        for (const parentId of asArray(word.upper_covers)) {
            if (liveWord(words, parentId)) adjacency[parentId].push(word.id);
        }
    }
    return adjacency;
}

function pathInAdjacency(adjacency, start, target, skipEdge = null) {
    if (start === target) return true;
    const seen = new Set([start]);
    const stack = [start];
    while (stack.length > 0) {
        const current = stack.pop();
        for (const next of adjacency[current] || []) {
            if (skipEdge && current === skipEdge[0] && next === skipEdge[1]) continue;
            if (next === target) return true;
            if (!seen.has(next)) {
                seen.add(next);
                stack.push(next);
            }
        }
    }
    return false;
}

export function hasPath(words, start, target, options = {}) {
    const adjacency = options.fromUpper === false
        ? words.map(word => word ? asArray(word.lower_covers) : [])
        : adjacencyFromUpper(words);
    return pathInAdjacency(adjacency, start, target, options.skipEdge || null);
}

export function findCoverCycle(words) {
    const adjacency = adjacencyFromUpper(words);
    const state = new Uint8Array(words.length);
    const stack = [];

    function visit(id) {
        state[id] = 1;
        stack.push(id);
        for (const childId of adjacency[id]) {
            if (state[childId] === 0) {
                const cycle = visit(childId);
                if (cycle) return cycle;
            } else if (state[childId] === 1) {
                const start = stack.indexOf(childId);
                return [...stack.slice(start), childId];
            }
        }
        stack.pop();
        state[id] = 2;
        return null;
    }

    for (const word of words) {
        if (word && state[word.id] === 0) {
            const cycle = visit(word.id);
            if (cycle) return cycle;
        }
    }
    return null;
}

function validateTextList(value, field, id, errors, { nullable = false } = {}) {
    if ((value === null || value === undefined) && nullable) return;
    if (!Array.isArray(value) || value.some(item => typeof item !== 'string')) {
        errors.push({ code: 'INVALID_FIELD_TYPE', id, field, message: `${field} は文字列配列でなければなりません` });
    }
}

function validateRichTextList(value, field, id, errors) {
    if (!Array.isArray(value) || value.some(item => !isPlainObject(item) || typeof item.title !== 'string' || typeof item.text !== 'string')) {
        errors.push({ code: 'INVALID_FIELD_TYPE', id, field, message: `${field} は {title, text} の配列でなければなりません` });
    }
}

export function validateDictionary(data) {
    const errors = [];
    const warnings = [];
    let words;
    try {
        words = requireDictionary(data);
    } catch (error) {
        return { valid: false, errors: [{ code: error.code, message: error.message }], warnings };
    }

    for (let index = 0; index < words.length; index++) {
        const word = words[index];
        if (word === null) continue;
        if (!isPlainObject(word)) {
            errors.push({ code: 'INVALID_WORD', id: index, message: '単語スロットはオブジェクトまたは null でなければなりません' });
            continue;
        }
        if (word.id !== index) errors.push({ code: 'ID_INDEX_MISMATCH', id: word.id, index, message: `id ${word.id} が配列位置 ${index} と一致しません` });
        if (typeof word.entry !== 'string') errors.push({ code: 'INVALID_FIELD_TYPE', id: index, field: 'entry', message: 'entry は文字列でなければなりません' });
        if (typeof word.category !== 'string') errors.push({ code: 'INVALID_FIELD_TYPE', id: index, field: 'category', message: 'category は文字列でなければなりません' });

        validateTextList(word.translations, 'translations', index, errors);
        validateTextList(word.simple_translations, 'simple_translations', index, errors, { nullable: true });
        validateTextList(word.tags, 'tags', index, errors);
        validateRichTextList(word.contents, 'contents', index, errors);
        validateRichTextList(word.variations, 'variations', index, errors);

        for (const field of ['upper_covers', 'lower_covers', 'arguments']) {
            const refs = word[field];
            if (!Array.isArray(refs) || refs.some(ref => !Number.isInteger(ref))) {
                errors.push({ code: 'INVALID_FIELD_TYPE', id: index, field, message: `${field} は整数IDの配列でなければなりません` });
                continue;
            }
            if (field !== 'arguments' && unique(refs).length !== refs.length) {
                errors.push({ code: 'DUPLICATE_REFERENCE', id: index, field, message: `${field} に重複したIDがあります` });
            }
            for (const ref of unique(refs)) {
                if (!liveWord(words, ref)) {
                    const issue = { code: 'DANGLING_REFERENCE', id: index, field, ref, message: `${field} が削除済みまたは存在しないID ${ref} を参照しています` };
                    if (field === 'arguments') warnings.push(issue);
                    else errors.push(issue);
                }
            }
        }

        if (word.relations !== null && word.relations !== undefined && !Array.isArray(word.relations)) {
            errors.push({ code: 'INVALID_FIELD_TYPE', id: index, field: 'relations', message: 'relations は配列または null でなければなりません' });
        } else {
            for (const relation of asArray(word.relations)) {
                if (!isPlainObject(relation) || typeof relation.title !== 'string' || !Number.isInteger(relation.entry)) {
                    errors.push({ code: 'INVALID_RELATION', id: index, relation, message: 'relation は文字列 title と整数 entry を持たなければなりません' });
                } else if (!liveWord(words, relation.entry)) {
                    warnings.push({ code: 'DANGLING_REFERENCE', id: index, field: 'relations', ref: relation.entry, message: `relations が削除済みまたは存在しないID ${relation.entry} を参照しています` });
                }
            }
        }

        const validFunctionValue = word.is_function === null
            || word.is_function === undefined
            || word.is_function === 0
            || typeof word.is_function === 'boolean';
        if (!validFunctionValue) {
            errors.push({ code: 'INVALID_FIELD_TYPE', id: index, field: 'is_function', message: 'is_function は真偽値または null でなければなりません' });
        }
        if (word.is_function === true && asArray(word.lower_covers).length > 0) {
            errors.push({ code: 'FUNCTION_HAS_CHILDREN', id: index, message: 'is_function=true の語に下位語を設定することはできません' });
        }
    }

    const idsByEntryAndCategory = new Map();
    for (const word of words) {
        if (!word || typeof word.entry !== 'string' || typeof word.category !== 'string') continue;
        const key = `${word.category}\0${word.entry}`;
        const ids = idsByEntryAndCategory.get(key) || [];
        ids.push(word.id);
        idsByEntryAndCategory.set(key, ids);
    }
    for (const [key, ids] of idsByEntryAndCategory) {
        if (ids.length > 1) {
            const [category, entry] = key.split('\0');
            warnings.push({
                code: 'DUPLICATE_ENTRY_IN_CATEGORY',
                entry,
                category,
                ids,
                message: `カテゴリ ${category} に同じ綴り ${entry} が複数存在します: ${ids.join(', ')}`,
            });
        }
    }

    if (errors.some(error => ['INVALID_WORD', 'INVALID_FIELD_TYPE', 'ID_INDEX_MISMATCH'].includes(error.code))) {
        return { valid: false, errors, warnings };
    }

    for (const word of words) {
        if (!word) continue;
        for (const parentId of word.upper_covers) {
            if (!liveWord(words, parentId)) continue;
            if (!words[parentId].lower_covers.includes(word.id)) {
                errors.push({
                    code: 'ASYMMETRIC_COVER',
                    id: word.id,
                    parent: parentId,
                    message: `${word.entry}(${word.id}) の上位語 ${words[parentId].entry}(${parentId}) に逆向きの lower_covers がありません`,
                });
            }
        }
        for (const childId of word.lower_covers) {
            if (!liveWord(words, childId)) continue;
            if (!words[childId].upper_covers.includes(word.id)) {
                errors.push({
                    code: 'ASYMMETRIC_COVER',
                    id: word.id,
                    child: childId,
                    message: `${word.entry}(${word.id}) の下位語 ${words[childId].entry}(${childId}) に逆向きの upper_covers がありません`,
                });
            }
        }
    }

    const sequenceCheck = sequenceCoverMismatches(words);
    errors.push(...sequenceCheck.errors, ...sequenceCheck.mismatches);

    const cycle = findCoverCycle(words);
    if (cycle) {
        errors.push({ code: 'CYCLE', ids: cycle, words: cycle.map(id => wordLabel(words, id)), message: `被覆関係に循環があります: ${cycle.join(' -> ')}` });
    } else {
        const adjacency = adjacencyFromUpper(words);
        for (const word of words) {
            if (!word) continue;
            for (const parentId of word.upper_covers) {
                if (!liveWord(words, parentId)) continue;
                if (pathInAdjacency(adjacency, parentId, word.id, [parentId, word.id])) {
                    errors.push({
                        code: 'REDUNDANT_COVER',
                        parent: parentId,
                        child: word.id,
                        message: `${words[parentId].entry}(${parentId}) -> ${word.entry}(${word.id}) は被覆関係ではなく冗長です`,
                    });
                }
            }
        }
        const placement = validatePlacement(words);
        errors.push(...placement.errors);
        warnings.push(...placement.warnings);
        const mitoshi = validateMitoshi(words);
        errors.push(...mitoshi.errors);
        warnings.push(...mitoshi.warnings);
    }

    return { valid: errors.length === 0, errors, warnings };
}

export function synchronizeLowerCovers(words) {
    const desired = Array.from({ length: words.length }, () => []);
    for (const word of words) {
        if (!word) continue;
        for (const parentId of asArray(word.upper_covers)) {
            requireLiveId(words, parentId, `upper_covers of ${word.id}`);
            desired[parentId].push(word.id);
        }
    }
    for (const word of words) {
        if (!word) continue;
        const desiredSet = new Set(desired[word.id]);
        const kept = unique(asArray(word.lower_covers)).filter(id => desiredSet.has(id));
        const keptSet = new Set(kept);
        word.lower_covers = [...kept, ...desired[word.id].filter(id => !keptSet.has(id))];
    }
}

export function reduceRedundantCovers(words) {
    const removed = [];
    let changed = true;
    while (changed) {
        changed = false;
        const adjacency = adjacencyFromUpper(words);
        outer: for (const word of words) {
            if (!word) continue;
            for (const parentId of [...word.upper_covers]) {
                if (pathInAdjacency(adjacency, parentId, word.id, [parentId, word.id])) {
                    word.upper_covers = word.upper_covers.filter(id => id !== parentId);
                    if (liveWord(words, parentId)) {
                        words[parentId].lower_covers = asArray(words[parentId].lower_covers).filter(id => id !== word.id);
                    }
                    removed.push({ parent: parentId, child: word.id });
                    changed = true;
                    break outer;
                }
            }
        }
    }
    return removed;
}

function inferCategory(words, parentIds) {
    if (parentIds.length === 0) return null;
    const categories = unique(parentIds.map(id => {
        const parent = words[id];
        return parent.category === 'カテゴリ' ? parent.entry : parent.category;
    }));
    if (categories.length !== 1) {
        throw new DictionaryOperationError('AMBIGUOUS_CATEGORY', '複数カテゴリにまたがる上位語から category を推定できません', { parentIds, categories });
    }
    return categories[0];
}

function normalizeNewWord(words, operation) {
    if (!isPlainObject(operation.word)) {
        throw new DictionaryOperationError('INVALID_OPERATION', 'add.word はオブジェクトでなければなりません');
    }
    const parentIds = operation.upper_covers || [];
    requireIdArray(words, parentIds, 'upper_covers');
    if (typeof operation.word.entry !== 'string' || operation.word.entry.length === 0) {
        throw new DictionaryOperationError('INVALID_FIELD', 'add.word.entry は空でない文字列でなければなりません');
    }
    const inferredCategory = inferCategory(words, parentIds);
    const category = operation.word.category ?? inferredCategory;
    if (typeof category !== 'string' || category.length === 0) {
        throw new DictionaryOperationError('INVALID_FIELD', '親を持たない語には category の指定が必要です');
    }
    if (inferredCategory && operation.word.category && operation.word.category !== inferredCategory) {
        throw new DictionaryOperationError('CATEGORY_MISMATCH', `指定 category ${operation.word.category} が上位語から推定される ${inferredCategory} と一致しません`);
    }

    const forbidden = ['id', 'upper_covers', 'lower_covers'];
    for (const field of forbidden) {
        if (field in operation.word) {
            throw new DictionaryOperationError('STRUCTURAL_FIELD', `add.word.${field} は直接指定できません`);
        }
    }

    return {
        id: words.length,
        entry: operation.word.entry,
        translations: operation.word.translations ?? [],
        simple_translations: operation.word.simple_translations ?? [],
        category,
        upper_covers: [...parentIds],
        lower_covers: [],
        arguments: operation.word.arguments ?? [],
        tags: operation.word.tags ?? [],
        contents: operation.word.contents ?? [],
        variations: operation.word.variations ?? [],
        relations: operation.word.relations ?? [],
        is_function: operation.word.is_function ?? false,
        ...(operation.word.partitions ? { partitions: structuredClone(operation.word.partitions) } : {}),
        ...(operation.word.cover_states ? { cover_states: structuredClone(operation.word.cover_states) } : {}),
        ...(operation.word.mitoshi_type ? { mitoshi_type: structuredClone(operation.word.mitoshi_type) } : {}),
        ...(operation.word.mitoshi_senses ? { mitoshi_senses: structuredClone(operation.word.mitoshi_senses) } : {}),
    };
}

function ensureNewReferencesAreLive(words, word) {
    requireIdArray(words, word.arguments, 'arguments', { allowDuplicates: true });
    for (const relation of asArray(word.relations)) {
        if (!isPlainObject(relation) || !Number.isInteger(relation.entry)) {
            throw new DictionaryOperationError('INVALID_RELATION', 'relations は整数 entry を持つオブジェクトの配列でなければなりません', { relation });
        }
        requireLiveId(words, relation.entry, 'relations.entry');
    }
}

function applyAdd(words, operation, assignedIds) {
    const word = normalizeNewWord(words, operation);
    words.push(word);
    ensureNewReferencesAreLive(words, word);
    for (const parentId of word.upper_covers) {
        words[parentId].lower_covers = unique([...asArray(words[parentId].lower_covers), word.id]);
    }
    if (operation.key !== undefined) assignedIds[String(operation.key)] = word.id;
}

function checkExpectedFields(word, operation, operationName) {
    if (!isPlainObject(operation.expect) || typeof operation.expect.entry !== 'string') {
        throw new DictionaryOperationError(
            'INVALID_OPERATION',
            `${operationName}.expect には削除・変更対象を確認する entry が必要です`,
        );
    }
    for (const [field, expected] of Object.entries(operation.expect)) {
        if (JSON.stringify(word[field]) !== JSON.stringify(expected)) {
            throw new DictionaryOperationError('PRECONDITION_FAILED', `${field} が expect と一致しません`, {
                id: operation.id,
                field,
                expected,
                actual: word[field],
            });
        }
    }
}

function applySetFields(words, operation) {
    requireLiveId(words, operation.id);
    if (!isPlainObject(operation.set) || Object.keys(operation.set).length === 0) {
        throw new DictionaryOperationError('INVALID_OPERATION', 'set_fields.set は1件以上のフィールドを持つオブジェクトでなければなりません');
    }
    const word = words[operation.id];
    if (operation.expect !== undefined) {
        if (!isPlainObject(operation.expect)) throw new DictionaryOperationError('INVALID_OPERATION', 'set_fields.expect はオブジェクトでなければなりません');
        for (const [field, expected] of Object.entries(operation.expect)) {
            if (JSON.stringify(word[field]) !== JSON.stringify(expected)) {
                throw new DictionaryOperationError('PRECONDITION_FAILED', `${field} が expect と一致しません`, { id: operation.id, field, expected, actual: word[field] });
            }
        }
    }
    for (const [field, value] of Object.entries(operation.set)) {
        if (!EDITABLE_FIELDS.has(field)) {
            throw new DictionaryOperationError('STRUCTURAL_FIELD', `${field} は set_fields で変更できません`, { field });
        }
        word[field] = structuredClone(value);
    }
    if ('arguments' in operation.set || 'relations' in operation.set) ensureNewReferencesAreLive(words, word);
}

function applySetUpperCovers(words, operation) {
    requireLiveId(words, operation.id);
    if (!Array.isArray(operation.from) || !Array.isArray(operation.to)) {
        throw new DictionaryOperationError('INVALID_OPERATION', 'set_upper_covers には from と to のID配列が必要です');
    }
    requireIdArray(words, operation.from, 'from');
    requireIdArray(words, operation.to, 'to');
    if (isSequenceWord(words[operation.id])) {
        throw new DictionaryOperationError('SEQUENCE_COVERS_DERIVED', '音列の被覆は綴りから導出されるので直接変更できません', { id: operation.id });
    }
    if (!sameSet(words[operation.id].upper_covers, operation.from)) {
        throw new DictionaryOperationError('PRECONDITION_FAILED', '現在の upper_covers が from と一致しません', {
            id: operation.id,
            expected: operation.from,
            actual: words[operation.id].upper_covers,
        });
    }
    if (operation.to.includes(operation.id)) {
        throw new DictionaryOperationError('SELF_COVER', '自分自身を上位語にはできません', { id: operation.id });
    }
    const inferredCategory = inferCategory(words, operation.to);
    if (inferredCategory && words[operation.id].category !== 'カテゴリ' && words[operation.id].category !== inferredCategory) {
        throw new DictionaryOperationError('CATEGORY_MISMATCH', `移動先カテゴリ ${inferredCategory} が語の category ${words[operation.id].category} と一致しません`);
    }
    // 対象語への既存の逆リンクを全て外してから、指定された両方向リンクを張る。
    // これにより、この明示操作だけが対象語の非対称状態を解消する。
    for (const candidate of words) {
        if (!candidate) continue;
        candidate.lower_covers = asArray(candidate.lower_covers).filter(id => id !== operation.id);
    }
    words[operation.id].upper_covers = [...operation.to];
    for (const parentId of operation.to) {
        words[parentId].lower_covers = unique([...asArray(words[parentId].lower_covers), operation.id]);
    }
}

function collectDeletionNeighborhood(words, id) {
    const victim = words[id];
    const parentIds = new Set(asArray(victim.upper_covers).filter(parentId => liveWord(words, parentId)));
    const childIds = new Set(asArray(victim.lower_covers).filter(childId => liveWord(words, childId)));
    const semanticReferences = [];

    for (const word of words) {
        if (!word || word.id === id) continue;
        if (asArray(word.lower_covers).includes(id)) parentIds.add(word.id);
        if (asArray(word.upper_covers).includes(id)) childIds.add(word.id);
        if (asArray(word.arguments).includes(id)) {
            semanticReferences.push({ id: word.id, entry: word.entry, field: 'arguments' });
        }
        if (asArray(word.relations).some(relation => relation?.entry === id)) {
            semanticReferences.push({ id: word.id, entry: word.entry, field: 'relations' });
        }
    }

    return { parentIds: [...parentIds], childIds: [...childIds], semanticReferences };
}

export function deleteWordInPlace(words, operation) {
    requireLiveId(words, operation.id);
    const victim = words[operation.id];
    checkExpectedFields(victim, operation, 'delete');
    if (!['none', 'parents'].includes(operation.reconnect)) {
        throw new DictionaryOperationError('INVALID_OPERATION', 'delete.reconnect は none または parents を明示してください');
    }
    if (!['reject', 'remove'].includes(operation.reference_policy)) {
        throw new DictionaryOperationError('INVALID_OPERATION', 'delete.reference_policy は reject または remove を明示してください');
    }

    const neighborhood = collectDeletionNeighborhood(words, operation.id);
    if (operation.reference_policy === 'reject' && neighborhood.semanticReferences.length > 0) {
        throw new DictionaryOperationError('WORD_IS_REFERENCED', '削除対象を参照する arguments または relations があります', {
            id: operation.id,
            references: neighborhood.semanticReferences,
        });
    }

    for (const word of words) {
        if (!word || word.id === operation.id) continue;
        word.upper_covers = asArray(word.upper_covers).filter(id => id !== operation.id);
        word.lower_covers = asArray(word.lower_covers).filter(id => id !== operation.id);
        if (operation.reference_policy === 'remove') {
            word.arguments = asArray(word.arguments).filter(id => id !== operation.id);
            if (Array.isArray(word.relations)) {
                word.relations = word.relations.filter(relation => relation?.entry !== operation.id);
            }
        }
    }
    words[operation.id] = null;
    pruneCoverStates(words);
    pruneMitoshi(words);

    if (operation.reconnect === 'parents') {
        for (const childId of neighborhood.childIds) {
            if (!liveWord(words, childId)) continue;
            for (const parentId of neighborhood.parentIds) {
                if (!liveWord(words, parentId) || childId === parentId) continue;
                // 既存の到達関係なら直結は冗長。逆向きの到達関係なら循環するため接続しない。
                if (hasPath(words, parentId, childId) || hasPath(words, childId, parentId)) continue;
                words[childId].upper_covers = unique([...asArray(words[childId].upper_covers), parentId]);
                words[parentId].lower_covers = unique([...asArray(words[parentId].lower_covers), childId]);
            }
        }
    }

    return neighborhood;
}

function applyMaterializeMitoshi(words, operation, assignedIds) {
    requireLiveId(words, operation.id);
    requireLiveId(words, operation.type, 'type');
    try {
        const newId = materializeMitoshiInPlace(words, operation, id => inferCategory(words, [id]));
        if (operation.key !== undefined) assignedIds[String(operation.key)] = newId;
    } catch (error) {
        if (error instanceof DictionaryOperationError) throw error;
        throw new DictionaryOperationError(error.code || 'INVALID_OPERATION', error.message, { id: operation.id, type: operation.type });
    }
}

function diffDictionaries(before, after) {
    const changes = [];
    const length = Math.max(before.words.length, after.words.length);
    for (let id = 0; id < length; id++) {
        const oldWord = before.words[id];
        const newWord = after.words[id];
        if (JSON.stringify(oldWord) === JSON.stringify(newWord)) continue;
        if (oldWord === undefined || oldWord === null) {
            changes.push({ type: 'add', id, after: newWord });
            continue;
        }
        if (newWord === undefined || newWord === null) {
            changes.push({ type: 'delete', id, before: oldWord });
            continue;
        }
        const fields = [];
        for (const field of unique([...Object.keys(oldWord), ...Object.keys(newWord)])) {
            if (JSON.stringify(oldWord[field]) !== JSON.stringify(newWord[field])) {
                fields.push({ field, before: oldWord[field], after: newWord[field] });
            }
        }
        changes.push({ type: 'update', id, entry: newWord.entry, fields });
    }
    return changes;
}

export function applyDictionaryPatch(data, patch) {
    requireDictionary(data);
    if (!isPlainObject(patch) || !Array.isArray(patch.operations)) {
        throw new DictionaryOperationError('INVALID_PATCH', 'パッチは operations 配列を持たなければなりません');
    }
    if (patch.version !== undefined && patch.version !== 1) {
        throw new DictionaryOperationError('UNSUPPORTED_PATCH_VERSION', `未対応のパッチバージョンです: ${patch.version}`);
    }

    const before = structuredClone(data);
    const next = structuredClone(data);
    const words = next.words;
    const assignedIds = {};

    for (let index = 0; index < patch.operations.length; index++) {
        const operation = patch.operations[index];
        try {
            if (!isPlainObject(operation) || typeof operation.op !== 'string') {
                throw new DictionaryOperationError('INVALID_OPERATION', '操作には op が必要です');
            }
            if (operation.op === 'add') applyAdd(words, operation, assignedIds);
            else if (operation.op === 'set_fields') applySetFields(words, operation);
            else if (operation.op === 'set_upper_covers') applySetUpperCovers(words, operation);
            else if (operation.op === 'delete') deleteWordInPlace(words, operation);
            else if (operation.op === 'materialize_mitoshi') applyMaterializeMitoshi(words, operation, assignedIds);
            else throw new DictionaryOperationError('UNKNOWN_OPERATION', `未知の操作です: ${operation.op}`);
        } catch (error) {
            if (error instanceof DictionaryOperationError) error.details = { operationIndex: index, ...error.details };
            throw error;
        }
    }

    const cycle = findCoverCycle(words);
    if (cycle) {
        throw new DictionaryOperationError('INTEGRITY_ERROR', 'パッチが被覆関係に循環を作ります', {
            errors: [{
                code: 'CYCLE',
                ids: cycle,
                words: cycle.map(id => wordLabel(words, id)),
                message: `被覆関係に循環があります: ${cycle.join(' -> ')}`,
            }],
            warnings: [],
        });
    }
    const derivedSequenceCovers = applyDerivedSequenceCovers(words);
    const removedRedundantCovers = reduceRedundantCovers(words);
    const prunedCoverStates = pruneCoverStates(words);
    const validation = validateDictionary(next);
    if (!validation.valid) {
        throw new DictionaryOperationError('INTEGRITY_ERROR', 'パッチ適用後の辞書が整合性条件を満たしません', validation);
    }

    return {
        data: next,
        changes: diffDictionaries(before, next),
        assignedIds,
        removedRedundantCovers,
        derivedSequenceCovers,
        prunedCoverStates,
        validation,
    };
}

export function resolveWordRef(data, ref) {
    const words = requireDictionary(data);
    if (Number.isInteger(ref)) {
        requireLiveId(words, ref);
        return words[ref];
    }
    if (typeof ref !== 'string') throw new DictionaryOperationError('INVALID_REF', '参照は id:123 または entry:語形 で指定してください');
    if (ref.startsWith('id:')) {
        const id = Number(ref.slice(3));
        requireLiveId(words, id);
        return words[id];
    }
    if (ref.startsWith('entry:')) {
        const entry = ref.slice(6);
        const matches = words.filter(word => word && word.entry === entry);
        if (matches.length === 0) throw new DictionaryOperationError('UNKNOWN_ENTRY', `綴りが見つかりません: ${entry}`);
        if (matches.length > 1) {
            throw new DictionaryOperationError('AMBIGUOUS_ENTRY', `綴りが一意ではありません: ${entry}`, { matches: matches.map(word => wordLabel(words, word.id)) });
        }
        return matches[0];
    }
    throw new DictionaryOperationError('INVALID_REF', '参照は id:123 または entry:語形 で指定してください', { ref });
}

export function summarizeWord(data, word, { full = false } = {}) {
    const words = requireDictionary(data);
    if (full) {
        return {
            ...structuredClone(word),
            upper_cover_words: asArray(word.upper_covers).map(id => wordLabel(words, id)),
            lower_cover_words: asArray(word.lower_covers).map(id => wordLabel(words, id)),
            argument_words: asArray(word.arguments).map(id => wordLabel(words, id)),
            relation_words: asArray(word.relations).map(relation => ({ ...relation, word: wordLabel(words, relation.entry) })),
            mitoshi_view: sensesOf(words, word.id).map(sense => ({
                ...sense,
                to_word: wordLabel(words, sense.to),
                target_word: sense.target === null ? null : wordLabel(words, sense.target),
            })),
        };
    }
    return {
        id: word.id,
        entry: word.entry,
        translations: asArray(word.translations),
        simple_translations: asArray(word.simple_translations),
        category: word.category,
        upper_covers: asArray(word.upper_covers).map(id => wordLabel(words, id)),
    };
}

function searchableText(word) {
    return [
        word.entry,
        ...asArray(word.translations),
        ...asArray(word.simple_translations),
        ...asArray(word.tags),
        ...asArray(word.contents).flatMap(item => [item.title, item.text]),
    ].join('\n').toLocaleLowerCase();
}

function includesText(values, query) {
    return asArray(values).some(value => String(value).toLocaleLowerCase().includes(query));
}

export function searchDictionary(data, options = {}) {
    const words = requireDictionary(data);
    const query = options.query?.toLocaleLowerCase() ?? null;
    const entry = options.entry?.toLocaleLowerCase() ?? null;
    const translation = options.translation?.toLocaleLowerCase() ?? null;
    const tag = options.tag?.toLocaleLowerCase() ?? null;
    const exact = options.exact === true;
    const limit = Math.max(1, Math.min(Number(options.limit) || 10, 100));
    const offset = Math.max(0, Number(options.offset) || 0);

    const matches = [];
    for (const word of words) {
        if (!word) continue;
        if (options.category && word.category !== options.category) continue;
        const wordEntry = word.entry.toLocaleLowerCase();
        const allTranslations = [...asArray(word.translations), ...asArray(word.simple_translations)];
        if (entry && (exact ? wordEntry !== entry : !wordEntry.includes(entry))) continue;
        if (translation && (exact ? !allTranslations.some(value => String(value).toLocaleLowerCase() === translation) : !includesText(allTranslations, translation))) continue;
        if (tag && (exact ? !asArray(word.tags).some(value => value.toLocaleLowerCase() === tag) : !includesText(word.tags, tag))) continue;
        if (query && !searchableText(word).includes(query)) continue;

        let score = 0;
        for (const needle of [query, entry, translation, tag].filter(Boolean)) {
            if (wordEntry === needle) score += 100;
            else if (wordEntry.startsWith(needle)) score += 60;
            else if (wordEntry.includes(needle)) score += 40;
            if (allTranslations.some(value => String(value).toLocaleLowerCase() === needle)) score += 80;
            else if (includesText(allTranslations, needle)) score += 30;
        }
        matches.push({ word, score });
    }

    matches.sort((a, b) => b.score - a.score || a.word.id - b.word.id);
    return {
        count: matches.length,
        offset,
        limit,
        truncated: offset + limit < matches.length,
        results: matches.slice(offset, offset + limit).map(({ word }) => summarizeWord(data, word)),
    };
}

function collectByDepth(words, startIds, direction, maxDepth) {
    const result = [];
    const seen = new Set();
    const frontier = startIds.map(id => ({ id, depth: 1 }));
    while (frontier.length > 0) {
        const current = frontier.shift();
        if (seen.has(current.id) || current.depth > maxDepth || !liveWord(words, current.id)) continue;
        seen.add(current.id);
        result.push({ depth: current.depth, ...wordLabel(words, current.id) });
        const nextIds = direction === 'up' ? words[current.id].upper_covers : words[current.id].lower_covers;
        frontier.push(...nextIds.map(id => ({ id, depth: current.depth + 1 })));
    }
    return result;
}

export function dictionaryContext(data, ref, options = {}) {
    const words = requireDictionary(data);
    const word = resolveWordRef(data, ref);
    const depth = Math.max(1, Math.min(Number(options.depth) || 1, 10));
    const limit = Math.max(1, Math.min(Number(options.limit) || 50, 100));
    const ancestors = collectByDepth(words, word.upper_covers, 'up', depth);
    const descendants = collectByDepth(words, word.lower_covers, 'down', depth);
    const usedAsArgumentBy = words
        .filter(candidate => candidate && asArray(candidate.arguments).includes(word.id))
        .map(candidate => wordLabel(words, candidate.id));
    const relatedFrom = words.flatMap(candidate => candidate
        ? asArray(candidate.relations)
            .filter(relation => relation.entry === word.id)
            .map(relation => ({ title: relation.title, ...wordLabel(words, candidate.id) }))
        : []);

    return {
        word: summarizeWord(data, word, { full: true }),
        depth,
        limit,
        ancestors: ancestors.slice(0, limit),
        descendants: descendants.slice(0, limit),
        used_as_argument_by: usedAsArgumentBy.slice(0, limit),
        related_from: relatedFrom.slice(0, limit),
        truncated: {
            ancestors: ancestors.length > limit,
            descendants: descendants.length > limit,
            used_as_argument_by: usedAsArgumentBy.length > limit,
            related_from: relatedFrom.length > limit,
        },
    };
}

function levenshtein(left, right) {
    const previous = Array.from({ length: right.length + 1 }, (_, index) => index);
    for (let i = 1; i <= left.length; i++) {
        let diagonal = previous[0];
        previous[0] = i;
        for (let j = 1; j <= right.length; j++) {
            const above = previous[j];
            previous[j] = Math.min(
                previous[j] + 1,
                previous[j - 1] + 1,
                diagonal + (left[i - 1] === right[j - 1] ? 0 : 1),
            );
            diagonal = above;
        }
    }
    return previous[right.length];
}

// 候補の中で音列が現れる位置（文字オフセット）．音素に分けられる候補では音素単位で照合し，
// tc の中の c のように音素をまたぐ一致を数えない．
function sequencePositions(candidateTokens, normalized, form) {
    const formTokens = tokenizePhonemes(form);
    if (!candidateTokens || !formTokens) {
        return [...normalized.matchAll(new RegExp(form.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'))].map(match => match.index);
    }
    const offsets = [];
    let offset = 0;
    for (let start = 0; start + formTokens.length <= candidateTokens.length; start++) {
        if (formTokens.every((token, k) => candidateTokens[start + k] === token)) offsets.push(offset);
        offset += candidateTokens[start].length;
    }
    return offsets;
}

export function analyzeForm(data, candidate, options = {}) {
    const words = requireDictionary(data);
    if (typeof candidate !== 'string' || candidate.length === 0) {
        throw new DictionaryOperationError('INVALID_FORM', '候補音列は空でない文字列でなければなりません');
    }
    const normalized = candidate.toLocaleLowerCase();
    const candidateTokens = tokenizePhonemes(normalized);
    const limit = Math.max(1, Math.min(Number(options.limit) || 10, 50));
    const exact = [];
    const containing = [];
    const registeredSequences = [];
    const similar = [];

    for (const word of words) {
        if (!word) continue;
        const form = word.entry.toLocaleLowerCase();
        if (form === normalized) exact.push(summarizeWord(data, word));
        else if (form.includes(normalized)) containing.push(summarizeWord(data, word));
        if (isSequenceWord(word) && form.length > 0) {
            const positions = sequencePositions(candidateTokens, normalized, form);
            if (positions.length > 0) registeredSequences.push({ ...summarizeWord(data, word), positions });
        }
        if (form !== normalized) {
            const distance = levenshtein(normalized, form);
            const threshold = Math.max(1, Math.floor(Math.max(normalized.length, form.length) / 4));
            if (distance <= threshold) similar.push({ distance, ...summarizeWord(data, word) });
        }
    }
    similar.sort((a, b) => a.distance - b.distance || a.id - b.id);
    registeredSequences.sort((a, b) => b.entry.length - a.entry.length || a.id - b.id);
    return {
        candidate,
        exact,
        containing: containing.slice(0, limit),
        registered_sequences: registeredSequences.slice(0, limit),
        similar: similar.slice(0, limit),
        truncated: {
            containing: containing.length > limit,
            registered_sequences: registeredSequences.length > limit,
            similar: similar.length > limit,
        },
    };
}

export function dictionaryStats(data) {
    const words = requireDictionary(data);
    const categories = {};
    const roots = [];
    for (const word of words) {
        if (!word) continue;
        categories[word.category] = (categories[word.category] || 0) + 1;
        if (asArray(word.upper_covers).length === 0) roots.push(wordLabel(words, word.id));
    }
    return {
        slots: words.length,
        live: words.filter(Boolean).length,
        deleted: words.filter(word => word === null).length,
        categories,
        roots,
    };
}

export function patchSchema() {
    return {
        version: 1,
        base_hash: 'validate または stats が返す SHA-256。--write 時は必須',
        operations: [
            {
                op: 'add',
                key: '任意の呼び名。assigned_ids に新IDが返る',
                upper_covers: [123],
                word: { entry: 'newword', translations: ['訳'], tags: [] },
            },
            {
                op: 'set_fields',
                id: 123,
                expect: { entry: 'oldword' },
                set: { entry: 'newword', translations: ['新しい訳'] },
            },
            {
                op: 'set_upper_covers',
                id: 123,
                from: [45],
                to: [67, 89],
            },
            {
                op: 'delete',
                id: 123,
                expect: { entry: 'oldword' },
                reconnect: 'parents',
                reference_policy: 'reject',
            },
            {
                op: 'materialize_mitoshi',
                key: '任意の呼び名。assigned_ids に新IDが返る',
                id: 123,
                type: 456,
            },
        ],
        editable_fields: [...EDITABLE_FIELDS],
        notes: [
            'id と lower_covers は直接編集できない',
            'set_upper_covers の from は現在値と集合として一致する必要がある',
            '構造操作は upper_covers と lower_covers を同時更新し、無関係な非対称リンクは自動修復しない',
            'delete は子の再接続方針と、arguments/relations 参照の扱いを必ず明示する',
            '明示操作の結果生じた冗長被覆は除去される',
            '音列の被覆は綴りから導出される（音素単位の連続部分列）。音列への set_upper_covers は拒否される',
            'cover_states: [{parent, state: 配置|暫定配置|未配置|上位未決, partition}]。記録のない辺は配置。partitions は親の側に置く',
            'materialize_mitoshi は語 id に当たる見做し型 type の仮想語義を、見做し先の直下に同じ綴りの語として作る',
        ],
    };
}
