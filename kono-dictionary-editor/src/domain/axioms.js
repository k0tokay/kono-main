// 公理レコード（辞書章「公理スキーマと整合性」）．
// 包摂 (H) は被覆辺，型付け (T) は arguments が担うので，ここには置かない．
// 語の axioms: [record]．record.kind ごとの形：
//   引き下げ: { relation, hub, projections: [k, l] }         … (D↓)(D↑)
//   スロット: { role, functional, total }                      … (S1)(S2)
//   定義:     { genus, differentia: [{ relation, value }] }   … この語 ≡ genus ⊓ ∃relation.value ⊓ …
//   式:       { text, refs: [id] }                             … スキーマの外（警告）
// どの kind も任意の note（本文の参照箇所など）を持てる．

import { assertedAncestors } from './placement.js';

export const AXIOM_KINDS = ['引き下げ', 'スロット', '定義', '式'];

const asArray = value => Array.isArray(value) ? value : [];
const isPlainObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);


/** レコードが参照する語ID（検証・削除時の掃除用）． */
export function axiomRefs(record) {
    if (!isPlainObject(record)) return [];
    switch (record.kind) {
        case '引き下げ': return [record.relation, record.hub, ...asArray(record.projections)];
        case 'スロット': return [record.role];
        case '定義': return [record.genus, ...asArray(record.differentia).flatMap(d => [d?.relation, d?.value])];
        case '式': return asArray(record.refs);
        default: return [];
    }
}

export function validateAxioms(words) {
    const errors = [];
    const warnings = [];
    const live = id => Number.isInteger(id) && Boolean(words[id]);

    for (const word of words) {
        if (!word || word.axioms === undefined || word.axioms === null) continue;
        const id = word.id;
        if (!Array.isArray(word.axioms)) {
            errors.push({ code: 'INVALID_FIELD_TYPE', id, field: 'axioms', message: 'axioms は配列です' });
            continue;
        }
        word.axioms.forEach((record, index) => {
            const at = { id, index };
            if (!isPlainObject(record) || !AXIOM_KINDS.includes(record.kind)) {
                errors.push({ code: 'INVALID_AXIOM', ...at, message: `公理の kind は ${AXIOM_KINDS.join('/')} のいずれかです` });
                return;
            }
            const refs = axiomRefs(record);
            if (record.kind === '引き下げ' && asArray(record.projections).length !== 2) {
                errors.push({ code: 'INVALID_AXIOM', ...at, message: '引き下げには射影が二つ要ります' });
            }
            if (record.kind === 'スロット') {
                for (const flag of ['functional', 'total']) {
                    if (typeof record[flag] !== 'boolean') errors.push({ code: 'INVALID_AXIOM', ...at, message: `スロットの ${flag} は真偽値です` });
                }
            }
            if (record.kind === '定義' && asArray(record.differentia).length === 0) {
                warnings.push({ code: 'DEFINITION_WITHOUT_DIFFERENTIA', ...at, message: `${word.entry}(${id}) の定義に種差がありません（属と同値になる）` });
            }
            if (record.kind === '式') {
                if (typeof record.text !== 'string' || record.text.trim() === '') errors.push({ code: 'INVALID_AXIOM', ...at, message: '式には text が要ります' });
                warnings.push({ code: 'AXIOM_OUTSIDE_SCHEMA', ...at, message: `${word.entry}(${id}) の公理「${record.text ?? ''}」は辞書公理スキーマの外にあり，整合性が構成的に保証されません` });
            }
            for (const ref of refs) {
                if (!live(ref)) errors.push({ code: 'INVALID_AXIOM', ...at, ref, message: `${word.entry}(${id}) の公理が生存しない語 ${ref} を参照しています` });
            }
            if (record.kind === '定義' && live(record.genus) && !assertedAncestors(words, id).has(record.genus)) {
                warnings.push({ code: 'DEFINITION_GENUS_NOT_ANCESTOR', ...at, message: `${word.entry}(${id}) の定義の属 ${words[record.genus].entry}(${record.genus}) が上位にありません` });
            }
        });
    }
    return { errors, warnings };
}

/** 削除された語を参照する公理を落とす（words を直接変更）． */
export function pruneAxioms(words) {
    const changed = [];
    for (const word of words) {
        if (!word || !Array.isArray(word.axioms)) continue;
        const kept = word.axioms.filter(record => axiomRefs(record).every(ref => ref == null || Boolean(words[ref])));
        if (kept.length !== word.axioms.length) {
            word.axioms = kept;
            changed.push(word.id);
        }
    }
    return changed;
}

/** 表示用の一行．label(id) は語の表示名を返す関数． */
export function formatAxiom(record, label) {
    switch (record?.kind) {
        case '引き下げ': return `${label(record.relation)} を ${label(record.hub)} へ引き下げ（射影 ${asArray(record.projections).map(label).join(', ')}）`;
        case 'スロット': return `${label(record.role)} は${record.functional ? '関数的' : '非関数的'}・${record.total ? '全域的' : '部分的'}`;
        case '定義': return `≡ ${label(record.genus)}${asArray(record.differentia).map(d => ` ⊓ ∃${label(d.relation)}.${label(d.value)}`).join('')}`;
        case '式': return record.text ?? '';
        default: return '（不明な公理）';
    }
}
