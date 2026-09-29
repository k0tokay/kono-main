// 分割（ファセット）と被覆辺ごとの配置の状態．
// 上位分類章「配置の状態」：被覆辺は包摂を主張する．ただし上位未決の辺は表示上の置き場で，
// 包摂を主張しない（理論上は概念の直下と同じ）．状態が変えるのは，上位の節点の分割の公理
// （排他・網羅）をその辺に適用するかどうかと，上位未決なら包摂そのものを主張するかどうかである．
//
// 節点側 partitions: [{ key, axis, kind, disjoint, exhaustive, basis, note }]
// 子の側 cover_states: [{ parent, state, partition }]
// cover_states に記録のない被覆辺は「配置」（分割は未宣言）とみなす．

export const PLACEMENT_STATES = ['配置', '暫定配置', '未配置', '上位未決'];
export const DEFAULT_STATE = '配置';
export const PARTITION_KINDS = ['骨格', '素性'];
export const PARTITION_BASES = ['推論', '区別', '選び分け'];
const STATES_WITH_PARTITION = new Set(['配置', '暫定配置']);

const asArray = value => Array.isArray(value) ? value : [];
const isPlainObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);

/** 包摂を主張する上位語（上位未決の辺を除く）． */
export function assertedParents(word) {
    return asArray(word?.upper_covers).filter(parentId => coverState(word, parentId).state !== '上位未決');
}

/** 包摂を主張する辺だけを辿った祖先の集合（自身は含まない）． */
export function assertedAncestors(words, id) {
    const seen = new Set();
    const stack = [...assertedParents(words[id])];
    while (stack.length) {
        const current = stack.pop();
        if (seen.has(current) || !words[current]) continue;
        seen.add(current);
        stack.push(...assertedParents(words[current]));
    }
    return seen;
}

/** 子 word から親 parentId への被覆辺の状態． */
export function coverState(word, parentId) {
    const record = asArray(word?.cover_states).find(r => r && r.parent === parentId);
    return {
        state: record?.state ?? DEFAULT_STATE,
        partition: record?.partition ?? null,
    };
}

export function findPartition(word, key) {
    return asArray(word?.partitions).find(p => p && p.key === key) || null;
}

/** cover_states から，もう被覆でない親への記録を取り除く（words を直接変更）． */
export function pruneCoverStates(words) {
    const pruned = [];
    for (const word of words) {
        if (!word || !Array.isArray(word.cover_states)) continue;
        const kept = word.cover_states.filter(r => r && asArray(word.upper_covers).includes(r.parent));
        if (kept.length !== word.cover_states.length) {
            pruned.push(word.id);
            word.cover_states = kept;
        }
    }
    return pruned;
}

/**
 * 被覆辺 (child -> parent) のうち，parent の排他的な分割に参加しているもの．
 * 返り値: Map<"parent\0key", Set<branchId>> を語ごとに作るための辺リスト．
 */
function disjointEdges(words) {
    const edges = new Map(); // childId -> [{ parent, key }]
    for (const word of words) {
        if (!word) continue;
        for (const record of asArray(word.cover_states)) {
            if (!record || record.partition == null) continue;
            if (!STATES_WITH_PARTITION.has(record.state)) continue;
            const parent = words[record.parent];
            const partition = findPartition(parent, record.partition);
            if (!partition || !partition.disjoint) continue;
            if (!edges.has(word.id)) edges.set(word.id, []);
            edges.get(word.id).push({ parent: record.parent, key: record.partition });
        }
    }
    return edges;
}

/**
 * 排他的な分割の二つ以上の枝の下に入る語を探す．
 * 語 w の祖先（w 自身を含む）c が，排他的分割 (p, k) の枝として p を被覆するとき，
 * c を w の (p, k) における枝と呼ぶ．枝が二つ以上あれば排他に反する．
 */
export function findDisjointnessViolations(words) {
    const edges = disjointEdges(words);
    if (edges.size === 0) return [];
    const violations = [];
    const memo = new Map(); // id -> Map<"p\0k", Set<branch>>

    const branchesOf = (id, visiting = new Set()) => {
        if (memo.has(id)) return memo.get(id);
        const result = new Map();
        if (visiting.has(id)) return result; // 循環は別の検査が扱う
        visiting.add(id);
        const word = words[id];
        for (const edge of edges.get(id) || []) {
            const k = `${edge.parent}\0${edge.key}`;
            if (!result.has(k)) result.set(k, new Set());
            result.get(k).add(id);
        }
        for (const parentId of assertedParents(word)) {
            if (!words[parentId]) continue;
            for (const [k, branches] of branchesOf(parentId, visiting)) {
                if (!result.has(k)) result.set(k, new Set());
                for (const b of branches) result.get(k).add(b);
            }
        }
        visiting.delete(id);
        memo.set(id, result);
        return result;
    };

    for (const word of words) {
        if (!word) continue;
        for (const [k, branches] of branchesOf(word.id)) {
            if (branches.size < 2) continue;
            const [parent, key] = k.split('\0');
            // 違反を最も上で報告する：枝のどれかの祖先側で既に違反していれば，その語だけを報告
            const parentWords = assertedParents(word).filter(p => words[p]);
            const inherited = parentWords.some(p => (branchesOf(p).get(k)?.size ?? 0) >= 2);
            if (inherited) continue;
            violations.push({
                code: 'DISJOINT_PARTITION_VIOLATION',
                id: word.id,
                entry: word.entry,
                parent: Number(parent),
                partition: key,
                branches: [...branches].sort((a, b) => a - b),
                message: `${word.entry}(${word.id}) が ${words[parent]?.entry}(${parent}) の排他的分割 ${key} の複数の枝 [${[...branches].join(', ')}] の下にあります`,
            });
        }
    }
    return violations;
}

/** partitions と cover_states の形・参照・排他を検査する． */
export function validatePlacement(words) {
    const errors = [];
    const warnings = [];

    for (const word of words) {
        if (!word) continue;
        const id = word.id;

        if (word.partitions !== undefined && word.partitions !== null) {
            if (!Array.isArray(word.partitions)) {
                errors.push({ code: 'INVALID_FIELD_TYPE', id, field: 'partitions', message: 'partitions は配列でなければなりません' });
            } else {
                const keys = new Set();
                for (const p of word.partitions) {
                    if (!isPlainObject(p) || typeof p.key !== 'string' || p.key.length === 0) {
                        errors.push({ code: 'INVALID_PARTITION', id, partition: p, message: '分割には空でない文字列 key が必要です' });
                        continue;
                    }
                    if (keys.has(p.key)) errors.push({ code: 'DUPLICATE_PARTITION', id, partition: p.key, message: `分割 ${p.key} が重複しています` });
                    keys.add(p.key);
                    if (p.kind !== undefined && !PARTITION_KINDS.includes(p.kind)) {
                        errors.push({ code: 'INVALID_PARTITION', id, partition: p.key, message: `分割の kind は ${PARTITION_KINDS.join('/')} のいずれかです` });
                    }
                    for (const flag of ['disjoint', 'exhaustive']) {
                        if (p[flag] !== undefined && typeof p[flag] !== 'boolean') {
                            errors.push({ code: 'INVALID_PARTITION', id, partition: p.key, message: `分割の ${flag} は真偽値です` });
                        }
                    }
                    if (p.basis !== undefined && (!Array.isArray(p.basis) || p.basis.some(b => !PARTITION_BASES.includes(b)))) {
                        errors.push({ code: 'INVALID_PARTITION', id, partition: p.key, message: `分割の basis は ${PARTITION_BASES.join('/')} の配列です` });
                    }
                    if (p.kind === '骨格' && !(p.basis?.length > 0)) {
                        warnings.push({ code: 'PARTITION_WITHOUT_BASIS', id, partition: p.key, message: `骨格の分割 ${p.key} に根拠（推論/区別/選び分け）がありません` });
                    }
                }
            }
        }

        if (word.cover_states !== undefined && word.cover_states !== null) {
            if (!Array.isArray(word.cover_states)) {
                errors.push({ code: 'INVALID_FIELD_TYPE', id, field: 'cover_states', message: 'cover_states は配列でなければなりません' });
                continue;
            }
            const seen = new Set();
            for (const record of word.cover_states) {
                if (!isPlainObject(record) || !Number.isInteger(record.parent)) {
                    errors.push({ code: 'INVALID_COVER_STATE', id, record, message: 'cover_states の要素は整数 parent を持つオブジェクトです' });
                    continue;
                }
                if (seen.has(record.parent)) errors.push({ code: 'DUPLICATE_COVER_STATE', id, parent: record.parent, message: `親 ${record.parent} への状態が重複しています` });
                seen.add(record.parent);
                if (!asArray(word.upper_covers).includes(record.parent)) {
                    errors.push({ code: 'COVER_STATE_NOT_A_COVER', id, parent: record.parent, message: `${word.entry}(${id}) の cover_states が被覆でない ${record.parent} を指しています` });
                    continue;
                }
                if (!PLACEMENT_STATES.includes(record.state)) {
                    errors.push({ code: 'INVALID_COVER_STATE', id, parent: record.parent, message: `状態は ${PLACEMENT_STATES.join('/')} のいずれかです` });
                    continue;
                }
                if (record.partition != null) {
                    if (!STATES_WITH_PARTITION.has(record.state)) {
                        errors.push({ code: 'PARTITION_ON_UNPLACED', id, parent: record.parent, message: `${record.state} の辺は分割に参加できません（包摂だけを主張する）` });
                    } else if (!findPartition(words[record.parent], record.partition)) {
                        errors.push({ code: 'UNKNOWN_PARTITION', id, parent: record.parent, partition: record.partition, message: `親 ${words[record.parent]?.entry}(${record.parent}) に分割 ${record.partition} がありません` });
                    }
                }
            }
        }
    }

    if (errors.length === 0) errors.push(...findDisjointnessViolations(words));
    return { errors, warnings };
}

/** 親 parentId の下の子を状態ごとに数える（木の表示用）． */
export function childStateCounts(words, parentId) {
    const counts = Object.fromEntries(PLACEMENT_STATES.map(s => [s, 0]));
    for (const childId of asArray(words[parentId]?.lower_covers)) {
        const child = words[childId];
        if (!child) continue;
        counts[coverState(child, parentId).state] += 1;
    }
    return counts;
}
