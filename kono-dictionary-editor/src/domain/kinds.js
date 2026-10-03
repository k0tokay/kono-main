// 種（概念を個体として扱う）：種への所属（⊏in，口語 dent）の生成と登録．
// detail/discussion/2026-10-03/kinds.tex，generation.tex，dictionary-root-codex-response.md．
//
// 所属は被覆辺（包摂 ⊑）と分けて表示する（2026-10-03 作者裁定：所属の表示）．
// 種 K の成員は保存せず，次から計算する．
// - 属性から：K の generator: { tArity, isFunc } に合うシグネチャの語 a の引用 ⌜a⌝
//   （例：konofon は1項述語 { tArity: 1, isFunc: false }，konomili は定数 { tArity: 1, isFunc: true }）．
// - 事実から：語の dent: [K]．
//     定数の語 c（関数で tArity 1）なら，c の値が K に属する（komatci dent [coto]：小町は人）．
//     それ以外の語 a なら，引用 ⌜a⌝ が K に属する（to dent [flentos]）．
// 同じ所属を属性と事実の両方で書かない（シグネチャで決まる所属を dent に書くと警告）．
//
// 実体化：引用 ⌜a⌝ に固有の情報を付けたいときだけ，⌜a⌝ を値とする定数の語を作る（quote_of: a）．
// 一つの語義の引用は一つだけ実体化できる．a の dent はその語へ移す．
// 実体化した語は被覆辺を持たず，所属（dent と，a のシグネチャから決まる種）で表示される．

const asArray = value => Array.isArray(value) ? value : [];
const isPlainObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);

/** 語のシグネチャ．is_function が真偽値でない，または関数なのに tArity が 0 の語は未設定（null）． */
export function signatureOf(word) {
    if (!word || typeof word.is_function !== 'boolean') return null;
    const tArity = asArray(word.arguments).length;
    if (word.is_function && tArity === 0) return null;
    return { tArity, isFunc: word.is_function };
}

export function isConstantWord(word) {
    const s = signatureOf(word);
    return Boolean(s) && s.isFunc && s.tArity === 1;
}

function isGenerator(value) {
    return isPlainObject(value) && Number.isInteger(value.tArity) && value.tArity >= 0 && typeof value.isFunc === 'boolean';
}

/** 語 a のシグネチャが種 kind の generator に合うか（kind と同じ category の語に限る）． */
export function generatedBySignature(words, kind, word) {
    if (!isGenerator(kind?.generator) || !word) return false;
    // 語彙目録 L の語だけを数える：種の語と同じ category の語（冠詞・括弧・慣用表現・音列は L でない）
    if (word.category !== kind.category) return false;
    const s = signatureOf(word);
    return Boolean(s) && s.tArity === kind.generator.tArity && s.isFunc === kind.generator.isFunc;
}

function quoteHolders(words) {
    const holder = new Map();
    for (const w of words) if (w && Number.isInteger(w.quote_of)) holder.set(w.quote_of, w.id);
    return holder;
}

/**
 * 種 kindId の成員．
 * { id: 表示する語, show: 'quote'（⌜id⌝ を仮想に出す）| 'word'（語そのものを出す）, source: 'signature'|'fact' }
 */
export function membersOf(words, kindId) {
    const kind = words[kindId];
    if (!kind) return [];
    const holder = quoteHolders(words);
    const out = [];
    for (const w of words) {
        if (!w) continue;
        if (Number.isInteger(w.quote_of)) {
            // 実体化した引用語：元の語のシグネチャか，自分の dent で所属する
            const bySignature = generatedBySignature(words, kind, words[w.quote_of]);
            const byFact = asArray(w.dent).includes(kindId);
            if (bySignature || byFact) out.push({ id: w.id, show: 'word', source: bySignature ? 'signature' : 'fact' });
            // その語自身も語彙の一つなので，その語の引用もシグネチャから生成される
            if (generatedBySignature(words, kind, w) && !holder.has(w.id)) out.push({ id: w.id, show: 'quote', source: 'signature' });
            continue;
        }
        const bySignature = generatedBySignature(words, kind, w) && !holder.has(w.id);
        const byFact = asArray(w.dent).includes(kindId);
        if (!bySignature && !byFact) continue;
        if (byFact && isConstantWord(w)) out.push({ id: w.id, show: 'word', source: 'fact' });
        else out.push({ id: w.id, show: 'quote', source: bySignature ? 'signature' : 'fact' });
    }
    return out;
}

/** 語 id（またはその引用）が属する種． */
export function kindsOf(words, id) {
    const word = words[id];
    if (!word) return [];
    const source = Number.isInteger(word.quote_of) ? words[word.quote_of] : word;
    const out = [];
    for (const k of words) {
        if (k && generatedBySignature(words, k, source)) out.push({ kind: k.id, source: 'signature' });
    }
    for (const k of asArray(word.dent)) out.push({ kind: k, source: 'fact' });
    return out;
}

export function validateKinds(words) {
    const errors = [];
    const warnings = [];
    const live = id => Number.isInteger(id) && Boolean(words[id]);
    const quoted = new Map();
    for (const word of words) {
        if (!word) continue;
        const id = word.id;
        if (word.generator !== undefined && word.generator !== null && !isGenerator(word.generator)) {
            errors.push({ code: 'INVALID_GENERATOR', id, message: `${word.entry}(${id}) の generator は { tArity: 0以上の整数, isFunc: 真偽 } です` });
        }
        const self = Number.isInteger(word.quote_of) && live(word.quote_of) ? words[word.quote_of] : word;
        if (word.dent !== undefined && word.dent !== null) {
            if (!Array.isArray(word.dent)) {
                errors.push({ code: 'INVALID_FIELD_TYPE', id, field: 'dent', message: 'dent は種の語IDの配列です' });
            } else {
                const seen = new Set();
                for (const k of word.dent) {
                    if (!live(k)) {
                        errors.push({ code: 'INVALID_DENT', id, kind: k, message: `${word.entry}(${id}) の dent が生存しない語 ${k} を指しています` });
                        continue;
                    }
                    if (seen.has(k)) errors.push({ code: 'DUPLICATE_DENT', id, kind: k, message: '同じ種への所属が重複しています' });
                    seen.add(k);
                    if (generatedBySignature(words, words[k], self)) {
                        warnings.push({ code: 'DENT_ALREADY_GENERATED', id, kind: k, message: `${word.entry}(${id}) の ${words[k].entry}(${k}) への所属はシグネチャから決まるので，dent に書く必要はありません` });
                    }
                }
            }
        }
        if (word.quote_of !== undefined && word.quote_of !== null) {
            if (!live(word.quote_of)) {
                errors.push({ code: 'INVALID_QUOTE_OF', id, message: `${word.entry}(${id}) の quote_of が生存する語を指していません` });
                continue;
            }
            if (!isConstantWord(word)) {
                warnings.push({ code: 'QUOTE_NOT_CONSTANT', id, message: `${word.entry}(${id}) は ⌜${words[word.quote_of].entry}⌝ を値とする定数（関数性あり，引数1つ）にします` });
            }
            if (asArray(word.upper_covers).length > 0) {
                warnings.push({ code: 'QUOTE_WITH_COVERS', id, message: `${word.entry}(${id}) は引用（個体）なので被覆辺を持たず，所属（dent）で種に置きます` });
            }
            if (asArray(words[word.quote_of].dent).length > 0) {
                warnings.push({ code: 'DENT_ON_QUOTED_SOURCE', id, message: `${words[word.quote_of].entry}(${word.quote_of}) の引用は実体化済みなので，所属は ${word.entry}(${id}) の dent に書きます` });
            }
            if (quoted.has(word.quote_of)) {
                errors.push({ code: 'DUPLICATE_QUOTE', id, other: quoted.get(word.quote_of), message: `⌜${words[word.quote_of].entry}⌝ が二度実体化されています` });
            } else {
                quoted.set(word.quote_of, id);
            }
        }
    }
    return { errors, warnings };
}

/** 引用 ⌜id⌝ を定数の語として実体化する（words を直接変更）．新しい語のIDを返す． */
export function materializeQuoteInPlace(words, { id, category }) {
    const source = words[id];
    if (!source) throw Object.assign(new Error('語が生存しません'), { code: 'INVALID_OPERATION' });
    if (Number.isInteger(source.quote_of)) throw Object.assign(new Error(`${source.entry} は既に引用の実体です`), { code: 'QUOTE_OF_QUOTE' });
    const existing = words.find(w => w && w.quote_of === id);
    if (existing) throw Object.assign(new Error(`⌜${source.entry}⌝ は既に ${existing.entry}(${existing.id}) として実体化されています`), { code: 'QUOTE_ALREADY_MATERIALIZED' });
    const newId = words.length;
    const dent = asArray(source.dent);
    words.push({
        id: newId,
        entry: `⌜${source.entry}⌝`,
        translations: [],
        simple_translations: [],
        category: category ?? source.category,
        upper_covers: [],
        lower_covers: [],
        arguments: [newId],
        tags: [],
        contents: [],
        variations: [],
        relations: [],
        is_function: true,
        quote_of: id,
        ...(dent.length ? { dent: [...dent] } : {}),
    });
    delete source.dent;
    return newId;
}

/** 削除で失われた種を指す dent を落とす（words を直接変更）． */
export function pruneKinds(words) {
    const changed = [];
    for (const word of words) {
        if (!word || !Array.isArray(word.dent)) continue;
        const kept = word.dent.filter(k => Boolean(words[k]));
        if (kept.length !== word.dent.length) {
            if (kept.length) word.dent = kept; else delete word.dent;
            changed.push(word.id);
        }
    }
    return changed;
}
