// 関係語のメタ性質（関係そのものの性質）．2項関係の語（arguments が2つで関数でない語）だけが持つ．
//
//   meta_props: {
//     functional: [arg],            // 関数的：arg 側の項が反対側の項を一意に決める
//     total_on: [{ node, arg }],    // 全域的：node の下の各 x（arg 側）に相手がある
//     symmetric: 真偽,              // 対称
//     transitive: 真偽,             // 推移
//     elidable: [arg],              // 見做し：arg 側から反対側への関係を文中で省略してよい
//   }
//
// arg は起点の項（1 なら x1 から x2 へ，2 なら x2 から x1 へ）．
// 見做し（省略可能）は，「家に入る」＝「家のある領域に入る」のように関係を挟まずに書くことを認める．
// 省略した相手が一つに決まる必要があるので，同じ向きの関数性・全域性がなければ警告する．

import { assertedAncestors } from './placement.js';

const asArray = value => Array.isArray(value) ? value : [];
const isPlainObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const ARGS = [1, 2];
const isArgList = value => Array.isArray(value) && value.every(a => ARGS.includes(a));

export function isRelationWord(word) {
    return Boolean(word) && asArray(word.arguments).length === 2 && !word.is_function;
}

export function validateMetaProps(words) {
    const errors = [];
    const warnings = [];
    const live = id => Number.isInteger(id) && Boolean(words[id]);
    for (const word of words) {
        if (!word || word.meta_props === undefined || word.meta_props === null) continue;
        const id = word.id;
        const m = word.meta_props;
        if (!isPlainObject(m)) {
            errors.push({ code: 'INVALID_FIELD_TYPE', id, field: 'meta_props', message: 'meta_props はオブジェクトです' });
            continue;
        }
        if (!isRelationWord(word)) {
            errors.push({ code: 'META_PROPS_ON_NON_RELATION', id, message: `${word.entry}(${id}) は2項関係の語ではないのでメタ性質を持てません` });
        }
        for (const field of ['functional', 'elidable']) {
            if (m[field] !== undefined && !isArgList(m[field])) errors.push({ code: 'INVALID_META_PROPS', id, message: `${field} は 1, 2 の配列です` });
        }
        for (const flag of ['symmetric', 'transitive']) {
            if (m[flag] !== undefined && typeof m[flag] !== 'boolean') errors.push({ code: 'INVALID_META_PROPS', id, message: `${flag} は真偽値です` });
        }
        const totalOn = m.total_on === undefined ? [] : m.total_on;
        if (!Array.isArray(totalOn)) {
            errors.push({ code: 'INVALID_META_PROPS', id, message: 'total_on は配列です' });
            continue;
        }
        for (const t of totalOn) {
            if (!isPlainObject(t) || !ARGS.includes(t.arg) || !live(t.node)) {
                errors.push({ code: 'INVALID_META_PROPS', id, record: t, message: `${word.entry}(${id}) の total_on は { node: 生存する語, arg: 1|2 } です` });
                continue;
            }
            const domain = asArray(word.arguments)[t.arg - 1];
            if (live(domain) && t.node !== domain && !assertedAncestors(words, t.node).has(domain)) {
                warnings.push({ code: 'TOTAL_ON_OUTSIDE_DOMAIN', id, node: t.node, message: `${word.entry}(${id}) の全域性の節点 ${words[t.node].entry}(${t.node}) が第${t.arg}項の型 ${words[domain].entry}(${domain}) の下にありません` });
            }
        }
        if (isArgList(m.elidable)) {
            for (const arg of m.elidable) {
                const functional = isArgList(m.functional) && m.functional.includes(arg);
                const total = totalOn.some(t => t?.arg === arg);
                if (!functional || !total) {
                    warnings.push({ code: 'ELIDABLE_NOT_DETERMINED', id, arg, message: `${word.entry}(${id}) は x${arg} からの省略を認めるが，その向きの${functional ? '' : '関数性'}${!functional && !total ? '・' : ''}${total ? '' : '全域性'}が宣言されていません（省略した相手が一つに決まらない）` });
                }
            }
        }
    }
    return { errors, warnings };
}

/** 削除で失われた語を指す total_on を落とす（words を直接変更）． */
export function pruneMetaProps(words) {
    const changed = [];
    for (const word of words) {
        if (!word || !isPlainObject(word.meta_props) || !Array.isArray(word.meta_props.total_on)) continue;
        const next = word.meta_props.total_on.filter(t => isPlainObject(t) && Boolean(words[t.node]));
        if (next.length !== word.meta_props.total_on.length) {
            word.meta_props = { ...word.meta_props, total_on: next };
            changed.push(word.id);
        }
    }
    return changed;
}

/** 表示用の一行． */
export function formatMetaProps(m, label) {
    if (!isPlainObject(m)) return '';
    const parts = [];
    for (const a of asArray(m.functional)) parts.push(`x${a} から関数的`);
    for (const t of asArray(m.total_on)) parts.push(`${label(t.node)} 上で x${t.arg} から全域的`);
    if (m.symmetric) parts.push('対称');
    if (m.transitive) parts.push('推移');
    for (const a of asArray(m.elidable)) parts.push(`x${a} から省略可（見做し）`);
    return parts.join('・');
}
