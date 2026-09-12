import { CATEGORY } from '../constants/categories.js';
import {
    findCoverCycle,
    hasPath as coreHasPath,
    reduceRedundantCovers,
} from '../domain/dictionaryCore.js';

export function createBlankWord(parentId, parentCategory, nextId) {
    const category = parentCategory === 'カテゴリ' ? parentCategory : parentCategory;
    return {
        id: nextId,
        entry: '',
        translations: [],
        category,
        upper_covers: [parentId],
        lower_covers: [],
        arguments: [],
        tags: [],
        contents: [],
        variations: [],
        relations: [],
        is_function: false
    };
}


export function search(dict, id, entry, translations) {
    if (Number(id) && dict.words[id]) {
        return [dict.words[id]];
    }

    const words = Object.values(dict.words);
    const result = [];

    for (let i = 0; i < words.length; i++) {
        if (words[i] === null) {
            continue;
        }

        const match = (query, item) => {
            if (query === null) {
                return true;
            } else if (typeof query === 'string') {
                try {
                    const regex = new RegExp(query);
                    return regex.test(item);
                } catch {
                    return item === query;
                }
            } else if (query instanceof RegExp) {
                return query.test(item);
            } else {
                return false;
            }
        };

        const entryMatches = match(entry, words[i].entry);

        const translationsMatches = match(translations, words[i].translations);

        if (entryMatches && translationsMatches) {
            result.push(words[i]);
        }
    }
    return result;
}

/** 再帰で「自分→祖先」をたどる関数 */
export function ancestorList(words, id, seen = new Set()) {
    if (seen.has(id)) return [];
    seen.add(id);
    const word = words[id];
    if (!word) return [];
    const parents = word.upper_covers || [];
    // 自分 + すべての祖先
    return [id, ...parents.flatMap(pid => ancestorList(words, pid, seen))];
}

/**
 * dict.words[start] → ... → dict.words[target] の経路があるか
 */
export function hasPath(start, target, dict, seen = new Set()) {
    return coreHasPath(dict.words, start, target, { fromUpper: false, seen });
}

/**
 * 周回がないか全要素チェック
 * @returns true: 循環なし, false: 循環あり (見つけたら即 false)
 */
export function hasNoCycle(dict, silent = false) {
    const cycle = findCoverCycle(dict.words);
    if (cycle && !silent) {
        const labels = cycle.map(id => `${dict.words[id]?.entry ?? '?'}(${id})`);
        alert(`循環検出: ${labels.join(' → ')}`);
    }
    return cycle === null;
}

export function allCoversAreMinimal(dict) {
    const { words } = dict;

    // helper – x–y エッジが冗長か?
    const isRedundant = (x, y, direction) => {
        for (const zWord of words) {
            if (!zWord) continue;
            const z = zWord.id;
            if (z === x || z === y) continue;

            if (direction === 'upper') {
                // y ≥ z ≥ x
                if (hasPath(y, z, dict) && hasPath(z, x, dict)) return true;
            } else {
                // x ≥ z ≥ y
                if (hasPath(x, z, dict) && hasPath(z, y, dict)) return true;
            }
        }
        return false;
    };

    for (const w of words) {
        if (!w) continue;
        const x = w.id;

        // ---- 上位被覆 ----
        for (const y of w.upper_covers || []) {
            if (isRedundant(x, y, 'upper')) {
                alert(
                    `非最短リンク: ${words[x].entry}(${x}) ←→ ${words[y].entry}(${y}) は冗長です`
                );
                return false;
            }
        }

        // ---- 下位被覆 ----
        for (const y of w.lower_covers || []) {
            if (isRedundant(x, y, 'lower')) {
                alert(
                    `非最短リンク: ${words[x].entry}(${x}) ←→ ${words[y].entry}(${y}) は冗長です`
                );
                return false;
            }
        }
    }
    return true;      // すべて即被覆
}


export function repairMinimalCovers(dict) {
    const { words } = dict;
    console.log('repairMinimalCovers:', words);

    // x–y エッジが冗長か判定（direction='upper' | 'lower'）
    const isRedundant = (x, y, direction) => {
        for (const zWord of words) {
            if (!zWord) continue;
            const z = zWord.id;
            if (z === x || z === y) continue;
            if (direction === 'upper') {
                // y ≥ z ≥ x
                if (hasPath(y, z, dict) && hasPath(z, x, dict)) return true;
            } else {
                // x ≥ z ≥ y
                if (hasPath(x, z, dict) && hasPath(z, y, dict)) return true;
            }
        }
        return false;
    };

    for (const w of words) {
        if (!w) continue;
        const x = w.id;

        // 1) upper_covers を修正
        {
            const kept = [];
            for (const y of w.upper_covers || []) {
                if (!words[y]) continue;
                if (isRedundant(x, y, 'upper')) {
                    words[y].lower_covers = (words[y].lower_covers || [])
                        .filter(id => id !== x);
                } else {
                    kept.push(y);
                }
            }
            w.upper_covers = Array.from(new Set(kept));

            for (const y of w.upper_covers) {
                if (!words[y]) continue;
                words[y].lower_covers = Array.from(
                    new Set(words[y].lower_covers || [])
                );
            }
        }

        // 2) lower_covers を修正
        {
            const kept = [];
            for (const y of w.lower_covers || []) {
                if (!words[y]) continue;
                if (isRedundant(x, y, 'lower')) {
                    words[y].upper_covers = (words[y].upper_covers || [])
                        .filter(id => id !== x);
                } else {
                    kept.push(y);
                }
            }
            w.lower_covers = Array.from(new Set(kept));

            for (const y of w.lower_covers) {
                if (!words[y]) continue;
                words[y].upper_covers = Array.from(
                    new Set(words[y].upper_covers || [])
                );
            }
        }
    }
}
export function removeRedundantEdges(dict) {
    const removed = reduceRedundantCovers(dict.words);
    if (removed.length > 0) {
        const { parent, child } = removed[0];
        alert(
            `冗長エッジ削除: ${dict.words[parent].entry}(${parent}) → ${dict.words[child].entry}(${child})`
        );
    }
    return removed.length > 0;
}

/**
 * 音列カテゴリの順序関係をチェック
 * @returns true: 全て正しい部分列関係, false: 誤ったリンクあり
 */
export function repairSubseqCovers(dict) {
    let allValid = true;
    const { words } = dict;

    for (const w of words) {
        if (!w || w.category !== CATEGORY.PHONEME_SEQ) continue;
        const s = w.entry;
        // 親一覧 (upper_covers) 側を検査
        const newUppers = [];
        for (const pid of w.upper_covers || []) {
            const p = words[pid];
            if (p && s.includes(p.entry)) {
                Array.from(new Set(newUppers).add(pid)); // 重複を除いて追加
            } else {
                allValid = false;
                // 親側の下位リンクからも除去
                if (p) p.lower_covers = p.lower_covers.filter(id => id !== w.id);
            }
        }
        w.upper_covers = newUppers;
    }

    return allValid;
}

export function checkIntegrity(dict) {
    const noCycle = hasNoCycle(dict);
    let minimalOk = false;
    let subseqOk = false;

    if (noCycle) { // 循環がなければ←それでいいのか？
        // 冗長エッジを削除できたか?
        const removed = removeRedundantEdges(dict);
        console.log('removed:', removed);

        // removed===false のとき「最短被覆だった」→ minimalOk=true
        minimalOk = !removed;

        // （音列の部分文字列チェックなどを入れる場合はここで）
        // subseqOk = repairSubseqCovers(dict) など
    }

    return { noCycle, minimalOk, subseqOk };
}

export const isValidWordTag = (words, wordId) => {
    if (wordId === null || wordId === undefined || wordId === "") {
        return false;
    }
    const num = Number(wordId);
    return Number.isInteger(num) && num >= 0 && words[num] !== null;
}
