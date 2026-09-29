// 音列カテゴリの被覆は手で張らず，綴りから導出する．
// 音列 a が音列 b の上位にあるのは，a の音素列が b の音素列の連続部分列であるとき．
// 被覆はその順序の Hasse 図（b の上位は，b に含まれる音列のうち極大なもの）．

// 綴りの音素目録．正は kono-phonology/konophon/data/phonology.toml の [[phonemes]] spell．
// test/soundSequences.test.js が toml との一致を検査する．
export const PHONEME_SPELLINGS = [
    'f', 's', 'z', 'c', 'zc', 'kh', 'h', 'ts', 'tc',
    'p', 'b', 't', 'd', 'k', 'g',
    'm', 'n', 'ng', 'l', 'w', 'j',
    'a', 'o', 'e', 'i', 'y', 'u', 'v',
];

export const SEQUENCE_CATEGORY = '音列';

const BY_LENGTH = [...PHONEME_SPELLINGS].sort((a, b) => b.length - a.length);

/** 綴りを最長一致で音素に分ける．分けられなければ null． */
export function tokenizePhonemes(spelling) {
    const out = [];
    let i = 0;
    while (i < spelling.length) {
        const hit = BY_LENGTH.find(p => spelling.startsWith(p, i));
        if (!hit) return null;
        out.push(hit);
        i += hit.length;
    }
    return out;
}

/** 音素列 a が音素列 b の連続部分列か（a = b も真）． */
export function isContiguousSubsequence(a, b) {
    if (a.length > b.length) return false;
    outer: for (let start = 0; start + a.length <= b.length; start++) {
        for (let k = 0; k < a.length; k++) {
            if (a[k] !== b[start + k]) continue outer;
        }
        return true;
    }
    return false;
}

export function sequenceRootId(words) {
    const root = words.find(w => w && w.category === 'カテゴリ' && w.entry === SEQUENCE_CATEGORY);
    return root ? root.id : null;
}

export function isSequenceWord(word) {
    return Boolean(word) && word.category === SEQUENCE_CATEGORY;
}

/**
 * 全音列の導出被覆を返す: Map<id, number[]>．
 * 音素化できない綴りは errors に入れ，その語の被覆は根に置く．
 */
export function deriveSequenceCovers(words) {
    const rootId = sequenceRootId(words);
    const covers = new Map();
    const errors = [];
    if (rootId === null) return { covers, errors, rootId };

    const items = [];
    for (const word of words) {
        if (!isSequenceWord(word)) continue;
        const tokens = tokenizePhonemes(word.entry);
        if (!tokens) {
            errors.push({ code: 'SEQUENCE_UNTOKENIZABLE', id: word.id, entry: word.entry, message: `音列 ${word.entry}(${word.id}) を音素に分けられません` });
            covers.set(word.id, [rootId]);
            continue;
        }
        if (tokens.length === 0) {
            // 編集途中の空の綴りは根に置き，他の音列の包含判定に使わない
            covers.set(word.id, [rootId]);
            continue;
        }
        items.push({ id: word.id, entry: word.entry, tokens });
    }

    for (const item of items) {
        // item に真に含まれる音列（綴りが同じ別語は含めない：重複は別の警告で扱う）
        const contained = items.filter(other => other.id !== item.id
            && other.tokens.length < item.tokens.length
            && isContiguousSubsequence(other.tokens, item.tokens));
        // 極大元：他の含まれる音列に真に含まれないもの
        const maximal = contained.filter(a => !contained.some(b => b !== a
            && b.tokens.length > a.tokens.length
            && isContiguousSubsequence(a.tokens, b.tokens)));
        covers.set(item.id, maximal.length > 0 ? maximal.map(m => m.id).sort((x, y) => x - y) : [rootId]);
    }
    return { covers, errors, rootId };
}

/** 導出被覆と現在の upper_covers の食い違い． */
export function sequenceCoverMismatches(words) {
    const { covers, errors } = deriveSequenceCovers(words);
    const mismatches = [];
    for (const [id, derived] of covers) {
        const actual = [...(words[id].upper_covers || [])].sort((x, y) => x - y);
        if (actual.length !== derived.length || actual.some((v, i) => v !== derived[i])) {
            mismatches.push({
                code: 'SEQUENCE_COVER_MISMATCH',
                id,
                entry: words[id].entry,
                expected: derived,
                actual,
                message: `音列 ${words[id].entry}(${id}) の被覆が綴りからの導出 [${derived.join(', ')}] と一致しません`,
            });
        }
    }
    return { mismatches, errors };
}

/** 音列の被覆を導出どおりに張り直す（words を直接変更）．変更した語のIDを返す． */
export function applyDerivedSequenceCovers(words) {
    const { covers } = deriveSequenceCovers(words);
    const changed = [];
    for (const [id, derived] of covers) {
        const word = words[id];
        const before = [...word.upper_covers].sort((x, y) => x - y);
        if (before.length === derived.length && before.every((v, i) => v === derived[i])) continue;
        for (const parentId of word.upper_covers) {
            if (words[parentId]) words[parentId].lower_covers = words[parentId].lower_covers.filter(c => c !== id);
        }
        word.upper_covers = [...derived];
        for (const parentId of derived) {
            if (!words[parentId].lower_covers.includes(id)) words[parentId].lower_covers.push(id);
        }
        changed.push(id);
    }
    return changed;
}
