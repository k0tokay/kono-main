// src/components/DetailFrame/AxiomForm.jsx
// 公理レコードの編集（辞書章「公理スキーマと整合性」）．包摂は上位語，型付けは引数が担う．
import { AXIOM_KINDS, formatAxiom } from '../../domain/axioms.js';
import { IdInput } from './IdInput';

const blank = kind => ({
    引き下げ: { kind, relation: null, hub: null, projections: [null, null], note: '' },
    スロット: { kind, role: null, functional: true, total: false, note: '' },
    定義: { kind, genus: null, differentia: [{ relation: null, value: null }], note: '' },
    式: { kind, text: '', refs: [], note: '' },
}[kind]);

function AxiomFields({ record, words, update }) {
    switch (record.kind) {
        case '引き下げ':
            return (
                <>
                    <div className="axiomRow"><span>関係</span><IdInput value={record.relation} words={words} onChange={v => update({ relation: v })} /></div>
                    <div className="axiomRow"><span>ハブ</span><IdInput value={record.hub} words={words} onChange={v => update({ hub: v })} /></div>
                    {[0, 1].map(i => (
                        <div key={i} className="axiomRow"><span>射影{i + 1}</span>
                            <IdInput value={record.projections?.[i]} words={words}
                                onChange={v => update({ projections: [0, 1].map(j => (j === i ? v : record.projections?.[j] ?? null)) })} />
                        </div>
                    ))}
                </>
            );
        case 'スロット':
            return (
                <>
                    <div className="axiomRow"><span>役割</span><IdInput value={record.role} words={words} onChange={v => update({ role: v })} /></div>
                    <div className="axiomRow">
                        <label><input type="checkbox" checked={Boolean(record.functional)} onChange={e => update({ functional: e.target.checked })} />関数的 (S1)</label>
                        <label><input type="checkbox" checked={Boolean(record.total)} onChange={e => update({ total: e.target.checked })} />全域的 (S2)</label>
                    </div>
                </>
            );
        case '定義': {
            const diff = record.differentia || [];
            const setDiff = next => update({ differentia: next });
            return (
                <>
                    <div className="axiomRow"><span>属</span><IdInput value={record.genus} words={words} onChange={v => update({ genus: v })} /></div>
                    {diff.map((d, i) => (
                        <div key={i} className="axiomRow"><span>種差</span>
                            <IdInput value={d.relation} words={words} placeholder="関係" onChange={v => setDiff(diff.map((x, j) => (j === i ? { ...x, relation: v } : x)))} />
                            <IdInput value={d.value} words={words} placeholder="値" onChange={v => setDiff(diff.map((x, j) => (j === i ? { ...x, value: v } : x)))} />
                            <button onClick={() => setDiff(diff.filter((_, j) => j !== i))}>×</button>
                        </div>
                    ))}
                    <button onClick={() => setDiff([...diff, { relation: null, value: null }])}>種差を追加</button>
                </>
            );
        }
        case '式':
            return (
                <textarea className="textForm" rows="2" placeholder="式（スキーマの外）" value={record.text ?? ''} onChange={e => update({ text: e.target.value })} />
            );
        default:
            return null;
    }
}

export function AxiomForm({ word, words, edited, onChange }) {
    const axioms = word.axioms || [];
    const set = next => onChange('axioms', next);
    const label = id => (id != null && words[id] ? words[id].entry : '?');
    return (
        <div className="largeListForm axiomForm">
            <div className="formHeader listHeader">
                <label className={edited ? 'edited' : ''}>公理</label>
                <select value="" onChange={e => e.target.value && set([...axioms, blank(e.target.value)])}>
                    <option value="">追加…</option>
                    {AXIOM_KINDS.map(k => <option key={k} value={k}>{k}</option>)}
                </select>
            </div>
            <div className="innerLargeListForm">
                {axioms.map((record, i) => (
                    <div key={i} className="largeListItem">
                        <div className="largeListItemHeader">
                            <button className="deleteItemBtn" onClick={() => set(axioms.filter((_, j) => j !== i))}>削除</button>
                            <span className="axiomKind">{record.kind}</span>
                            <span className="axiomSummary">{formatAxiom(record, label)}</span>
                        </div>
                        <AxiomFields record={record} words={words} update={patch => set(axioms.map((r, j) => (j === i ? { ...r, ...patch } : r)))} />
                        <input className="textForm" placeholder="注（本文の参照箇所など）" value={record.note ?? ''}
                            onChange={e => set(axioms.map((r, j) => (j === i ? { ...r, note: e.target.value } : r)))} />
                    </div>
                ))}
            </div>
        </div>
    );
}
