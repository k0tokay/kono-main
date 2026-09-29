// src/components/DetailFrame/PlacementForms.jsx
// 被覆辺ごとの配置の状態と，節点の分割（ファセット）の編集フォーム．
import {
    PLACEMENT_STATES, PARTITION_KINDS, PARTITION_BASES, coverState, findPartition,
} from '../../domain/placement.js';

const STATES_WITH_PARTITION = new Set(['配置', '暫定配置']);

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
                                {partitions.map(p => <option key={p.key} value={p.key}>{p.key}{p.axis ? `：${p.axis}` : ''}</option>)}
                            </select>
                            {partition && !findPartition(parent, partition) && <span className="warn">分割が見つかりません</span>}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

const blankPartition = () => ({ key: '', axis: '', kind: '骨格', disjoint: true, exhaustive: false, basis: [], note: '' });

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
                            <button className="deleteItemBtn" onClick={() => set(partitions.filter((_, j) => j !== i))}>削除</button>
                            <input className="textForm" placeholder="key" value={p.key} onChange={e => updateAt(i, { key: e.target.value })} />
                            <input className="textForm" placeholder="軸" value={p.axis ?? ''} onChange={e => updateAt(i, { axis: e.target.value })} />
                            <select value={p.kind ?? '骨格'} onChange={e => updateAt(i, { kind: e.target.value })}>
                                {PARTITION_KINDS.map(k => <option key={k} value={k}>{k}</option>)}
                            </select>
                        </div>
                        <div className="partitionFlags">
                            <label><input type="checkbox" checked={Boolean(p.disjoint)} onChange={e => updateAt(i, { disjoint: e.target.checked })} />排他</label>
                            <label><input type="checkbox" checked={Boolean(p.exhaustive)} onChange={e => updateAt(i, { exhaustive: e.target.checked })} />網羅</label>
                            <span className="basisLabel">根拠：</span>
                            {PARTITION_BASES.map(b => (
                                <label key={b}>
                                    <input
                                        type="checkbox"
                                        checked={(p.basis || []).includes(b)}
                                        onChange={e => updateAt(i, {
                                            basis: e.target.checked ? [...(p.basis || []), b] : (p.basis || []).filter(x => x !== b),
                                        })}
                                    />{b}
                                </label>
                            ))}
                            <span className="memberCount">枝 {members(p.key).length}</span>
                        </div>
                        <textarea className="textForm" rows="2" placeholder="注（本文の参照箇所など）" value={p.note ?? ''} onChange={e => updateAt(i, { note: e.target.value })} />
                    </div>
                ))}
            </div>
        </div>
    );
}
