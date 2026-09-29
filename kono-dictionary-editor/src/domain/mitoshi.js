// 見做し（上位分類章「語彙化：見做し」）：存在論上の二つの節点，それを結ぶ二項関係，
// 両端を呼び分けないという語彙化の決定の三点セット．
//
// 見做しの型は「見做し」カテゴリの語として置き，mitoshi_type を持つ：
//   { from: 節点ID, to: 節点ID, relation: 関係語ID | null, uniform: 真偽 }
// uniform な型は from の真の子孫すべてに to 側の語義を生やす（移行がクラス全体に一様）．
// 一様でない型は，語の mitoshi_senses で個別に当てる．
//
// 語の mitoshi_senses: [{ type: 見做し型ID, target: 実体化した語ID | null, exclude: 真偽 }]
//   target が null の語義は仮想（計算で表示するだけ）．独自の子や公理が要るときに実体化する．
//   exclude は uniform な型をその語にだけ当てないための印．

export const MITOSHI_CATEGORY = '見做し';

const asArray = value => Array.isArray(value) ? value : [];
const isPlainObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);

export function isMitoshiType(word) {
    return Boolean(word) && word.category === MITOSHI_CATEGORY && isPlainObject(word.mitoshi_type);
}

export function mitoshiTypes(words) {
    return words.filter(isMitoshiType);
}

function ancestorsOf(words, id) {
    const seen = new Set();
    const stack = [...asArray(words[id]?.upper_covers)];
    while (stack.length) {
        const current = stack.pop();
        if (seen.has(current) || !words[current]) continue;
        seen.add(current);
        stack.push(...asArray(words[current].upper_covers));
    }
    return seen;
}

/** 語 id に当たる見做し語義（仮想と実体化済みの両方）． */
export function sensesOf(words, id) {
    const word = words[id];
    if (!word || word.category === MITOSHI_CATEGORY || word.category === 'カテゴリ') return [];
    const ancestors = ancestorsOf(words, id);
    const records = new Map(asArray(word.mitoshi_senses).filter(isPlainObject).map(r => [r.type, r]));
    const senses = [];
    for (const type of mitoshiTypes(words)) {
        const { from, to, relation = null, uniform = false } = type.mitoshi_type;
        const record = records.get(type.id);
        const applies = (uniform && ancestors.has(from)) || (record && !record.exclude);
        if (!applies || record?.exclude) continue;
        senses.push({
            source: id,
            type: type.id,
            type_entry: type.entry,
            entry: word.entry,
            to,
            relation,
            uniform: Boolean(uniform),
            target: record?.target ?? null,
        });
    }
    return senses;
}

/** 辞書全体の仮想語義（実体化されていないもの）． */
export function virtualSenses(words) {
    const out = [];
    for (const word of words) {
        if (!word) continue;
        for (const sense of sensesOf(words, word.id)) if (sense.target === null) out.push(sense);
    }
    return out;
}

export function validateMitoshi(words) {
    const errors = [];
    const warnings = [];
    const live = id => Number.isInteger(id) && Boolean(words[id]);

    for (const word of words) {
        if (!word) continue;
        if (word.category === MITOSHI_CATEGORY && word.mitoshi_type !== undefined && word.mitoshi_type !== null) {
            const t = word.mitoshi_type;
            if (!isPlainObject(t)) {
                errors.push({ code: 'INVALID_MITOSHI_TYPE', id: word.id, message: 'mitoshi_type はオブジェクトです' });
            } else {
                if (!live(t.from) || !live(t.to)) errors.push({ code: 'INVALID_MITOSHI_TYPE', id: word.id, message: `見做し型 ${word.entry}(${word.id}) の from/to が生存する語を指していません` });
                else if (t.from === t.to) errors.push({ code: 'INVALID_MITOSHI_TYPE', id: word.id, message: `見做し型 ${word.entry}(${word.id}) の from と to が同じです` });
                if (t.relation != null && !live(t.relation)) errors.push({ code: 'INVALID_MITOSHI_TYPE', id: word.id, message: `見做し型 ${word.entry}(${word.id}) の relation が生存する語を指していません` });
                if (t.uniform !== undefined && typeof t.uniform !== 'boolean') errors.push({ code: 'INVALID_MITOSHI_TYPE', id: word.id, message: 'uniform は真偽値です' });
            }
        }
        if (word.mitoshi_senses === undefined || word.mitoshi_senses === null) continue;
        if (!Array.isArray(word.mitoshi_senses)) {
            errors.push({ code: 'INVALID_FIELD_TYPE', id: word.id, field: 'mitoshi_senses', message: 'mitoshi_senses は配列です' });
            continue;
        }
        const seen = new Set();
        for (const record of word.mitoshi_senses) {
            if (!isPlainObject(record) || !isMitoshiType(words[record.type])) {
                errors.push({ code: 'INVALID_MITOSHI_SENSE', id: word.id, record, message: `${word.entry}(${word.id}) の mitoshi_senses が見做し型でない語を指しています` });
                continue;
            }
            if (seen.has(record.type)) errors.push({ code: 'DUPLICATE_MITOSHI_SENSE', id: word.id, type: record.type, message: '同じ見做し型が重複しています' });
            seen.add(record.type);
            if (record.target == null) continue;
            if (record.exclude) {
                errors.push({ code: 'INVALID_MITOSHI_SENSE', id: word.id, type: record.type, message: '除外した見做しに実体化先は持てません' });
                continue;
            }
            if (!live(record.target)) {
                errors.push({ code: 'INVALID_MITOSHI_SENSE', id: word.id, type: record.type, message: `実体化先 ${record.target} が生存しません` });
                continue;
            }
            const to = words[record.type].mitoshi_type.to;
            if (record.target !== to && !ancestorsOf(words, record.target).has(to)) {
                errors.push({ code: 'MITOSHI_TARGET_OUTSIDE', id: word.id, type: record.type, target: record.target, message: `実体化先 ${words[record.target].entry}(${record.target}) が見做し先 ${words[to]?.entry}(${to}) の下にありません` });
            }
            if (words[record.target].entry !== word.entry) {
                warnings.push({ code: 'MITOSHI_ENTRY_DIFFERS', id: word.id, target: record.target, message: `見做しで結んだ ${word.entry}(${word.id}) と ${words[record.target].entry}(${record.target}) の綴りが違います（見做しは呼び分けない語彙化）` });
            }
        }
    }
    return { errors, warnings };
}

/**
 * 仮想語義を実体化する（words を直接変更）．新しい語のIDを返す．
 * 新しい語は見做し先 to の直下に，同じ綴り・訳で作り，relations で元の語へ結ぶ．
 */
export function materializeMitoshiInPlace(words, { id, type }, categoryOf) {
    const sense = sensesOf(words, id).find(s => s.type === type);
    if (!sense) throw Object.assign(new Error(`語 ${id} に見做し型 ${type} は当たりません`), { code: 'MITOSHI_NOT_APPLICABLE' });
    if (sense.target !== null) throw Object.assign(new Error(`見做し型 ${type} は既に ${sense.target} に実体化されています`), { code: 'MITOSHI_ALREADY_MATERIALIZED' });
    const source = words[id];
    const newId = words.length;
    words.push({
        id: newId,
        entry: source.entry,
        translations: [...asArray(source.translations)],
        simple_translations: [],
        category: categoryOf(sense.to),
        upper_covers: [sense.to],
        lower_covers: [],
        arguments: [newId],
        tags: [],
        contents: [{ title: '見做し', text: `${source.entry}(${id}) から見做し「${sense.type_entry}」で実体化` }],
        variations: [],
        relations: [{ title: sense.type_entry, entry: id }],
        is_function: false,
    });
    words[sense.to].lower_covers = [...asArray(words[sense.to].lower_covers), newId];
    const others = asArray(source.mitoshi_senses).filter(r => r?.type !== type);
    source.mitoshi_senses = [...others, { type, target: newId, exclude: false }];
    return newId;
}

/** 削除などで失われた見做し型・実体化先への参照を掃除する（words を直接変更）． */
export function pruneMitoshi(words) {
    const changed = [];
    for (const word of words) {
        if (!word || !Array.isArray(word.mitoshi_senses)) continue;
        const next = word.mitoshi_senses
            .filter(r => isPlainObject(r) && isMitoshiType(words[r.type]))
            .map(r => (r.target != null && !words[r.target] ? { ...r, target: null } : r));
        if (JSON.stringify(next) !== JSON.stringify(word.mitoshi_senses)) {
            word.mitoshi_senses = next;
            changed.push(word.id);
        }
    }
    return changed;
}
