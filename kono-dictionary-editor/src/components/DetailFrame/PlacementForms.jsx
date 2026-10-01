// src/components/DetailFrame/PlacementForms.jsx
// 被覆辺ごとの配置の状態と，節点の分割（ファセット）の編集フォーム．
import {
    PLACEMENT_STATES, PARTITION_KINDS, coverState, findPartition, isDisjoint,
} from '../../domain/placement.js';

const STATES_WITH_PARTITION = new Set(['配置']);

/** 上位語ごとに状態と分割を選ぶ． */
export function CoverStateForm({ word, words, edited, onChange, onClick }) {
    const parents = (word.upper_covers || []).filter(id => words[id]);
    if (parents.length === 0) return null;

    const update = (parentId, patch) => {
        const current = coverState(word, parentId);
        const next = { parent: parentId, ...current, ...patch };
        if (!STATES_WITH_PARTITION.has(next.state)) next.partition = null;
        const others = (word.cover_states || []).filter(r => r.parent !== parentId && parents.includes(r.parent));
        // 既定（配置・分割なし）に戻ったら記録を消す
        const isDefault = next.state === '配置' && next.partition == null;
        onChange('cover_states', isDefault ? others : [...others, next].sort((a, b) => a.parent - b.parent));
    };

    return (
        <div className="largeListForm coverStateForm">
            <div className="formHeader listHeader">
                <label className={edited ? 'edited' : ''}>被覆の状態</label>
            </div>
            <div className="innerLargeListForm">
                {parents.map(parentId => {
                    const parent = words[parentId];
                    const { state, partition } = coverState(word, parentId);
                    const partitions = parent.partitions || [];
                    return (
                        <div key={parentId} className="coverStateRow">
                            <span className="parentLabel" onClick={() => onClick(parentId)}>
                                <span className="id">{parentId}</span> {parent.entry}
                            </span>
                            <select value={state} onChange={e => update(parentId, { state: e.target.value })}>
                                {PLACEMENT_STATES.map(s => <option key={s} value={s}>{s}</option>)}
                            </select>
                            <select
                                value={partition ?? ''}
                                disabled={!STATES_WITH_PARTITION.has(state) || partitions.length === 0}
                                onChange={e => update(parentId, { partition: e.target.value || null })}
                            >
                                <option value="">（分割なし）</option>
                                {partitions.map(p => <option key={p.key} value={p.key}>{p.key}</option>)}
                            </select>
                            {partition && !findPartition(parent, partition) && <span className="warn">分割が見つかりません</span>}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

const blankPartition = () => ({ key: '', kind: 'コンストラクタ', disjoint: true, exhaustive: false, note: '' });

/** この節点が持つ分割の一覧． */
export function PartitionForm({ word, words, edited, onChange }) {
    const partitions = word.partitions || [];
    const set = next => onChange('partitions', next);
    const updateAt = (i, patch) => set(partitions.map((p, j) => (j === i ? { ...p, ...patch } : p)));
    const members = key => (word.lower_covers || []).filter(childId => {
        const child = words[childId];
        return child && coverState(child, word.id).partition === key;
    });

    return (
        <div className="largeListForm partitionForm">
            <div className="formHeader listHeader">
                <label className={edited ? 'edited' : ''}>分割</label>
                <button onClick={() => set([...partitions, blankPartition()])}>追加</button>
            </div>
            <div className="innerLargeListForm">
                {partitions.map((p, i) => (
                    <div key={i} className="largeListItem">
                        <div className="largeListItemHeader">
                            <input className="lineInput itemTitle" placeholder="名前" value={p.key} onChange={e => updateAt(i, { key: e.target.value })} />
                            <select value={p.kind ?? 'コンストラクタ'} onChange={e => updateAt(i, { kind: e.target.value })}>
                                {PARTITION_KINDS.map(k => <option key={k} value={k}>{k}</option>)}
                            </select>
                            <button className="deleteItemBtn" onClick={() => set(partitions.filter((_, j) => j !== i))}>削除</button>
                        </div>
                        <div className="largeListItemHeader partitionFlags">
                            <label><input type="checkbox" checked={isDisjoint(p)} disabled={p.kind === 'コンストラクタ'} onChange={e => updateAt(i, { disjoint: e.target.checked })} />排他</label>
                            <label><input type="checkbox" checked={Boolean(p.exhaustive)} onChange={e => updateAt(i, { exhaustive: e.target.checked })} />網羅</label>
                            <span className="memberCount">枝 {members(p.key).length}</span>
                        </div>
                        <textarea className="lineInput" rows="3" placeholder="注（本文の参照箇所など）" value={p.note ?? ''} onChange={e => updateAt(i, { note: e.target.value })} />
                    </div>
                ))}
            </div>
        </div>
    );
}
