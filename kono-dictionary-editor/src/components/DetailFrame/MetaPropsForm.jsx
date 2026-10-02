// src/components/DetailFrame/MetaPropsForm.jsx
// 2項関係の語のメタ性質：関数的・全域的・対称・推移・見做し（省略可能）．
import { isRelationWord } from '../../domain/metaProps.js';
import { IdInput } from './IdInput';

const ARGS = [1, 2];

function ArgSelect({ value, onChange }) {
    return (
        <select value={value ?? 1} onChange={e => onChange(Number(e.target.value))}>
            <option value={1}>x1 から</option>
            <option value={2}>x2 から</option>
        </select>
    );
}

export function MetaPropsForm({ word, words, edited, onChange }) {
    if (!isRelationWord(word)) return null;
    const m = word.meta_props || {};
    const set = patch => {
        const next = { ...m, ...patch };
        for (const key of Object.keys(next)) {
            const v = next[key];
            if (v === false || (Array.isArray(v) && v.length === 0)) delete next[key];
        }
        onChange('meta_props', Object.keys(next).length ? next : undefined);
    };
    const toggleArg = (field, arg) => {
        const list = m[field] || [];
        set({ [field]: list.includes(arg) ? list.filter(a => a !== arg) : [...list, arg].sort() });
    };
    const totalOn = m.total_on || [];
    const setTotalAt = (i, patch) => set({ total_on: totalOn.map((t, j) => (j === i ? { ...t, ...patch } : t)) });

    return (
        <div className="largeListForm metaPropsForm">
            <div className="formHeader listHeader">
                <label className={edited ? 'edited' : ''}>メタ性質</label>
                <button onClick={() => set({ total_on: [...totalOn, { node: word.arguments?.[0] ?? null, arg: 1 }] })}>全域性</button>
            </div>
            <div className="innerLargeListForm">
                {ARGS.map(arg => (
                    <div key={arg} className="largeListItemHeader metaFlags">
                        <span className="rowLabel">x{arg} から</span>
                        <label><input type="checkbox" checked={(m.functional || []).includes(arg)} onChange={() => toggleArg('functional', arg)} />関数的</label>
                        <label><input type="checkbox" checked={(m.elidable || []).includes(arg)} onChange={() => toggleArg('elidable', arg)} />見做し（省略可）</label>
                    </div>
                ))}
                <div className="largeListItemHeader metaFlags">
                    <label><input type="checkbox" checked={Boolean(m.symmetric)} onChange={e => set({ symmetric: e.target.checked })} />対称</label>
                    <label><input type="checkbox" checked={Boolean(m.transitive)} onChange={e => set({ transitive: e.target.checked })} />推移</label>
                </div>
                {totalOn.map((t, i) => (
                    <div key={i} className="largeListItemHeader">
                        <span className="rowLabel">全域的</span>
                        <IdInput value={t.node} words={words} onChange={v => setTotalAt(i, { node: v })} />
                        <ArgSelect value={t.arg} onChange={v => setTotalAt(i, { arg: v })} />
                        <button className="deleteItemBtn" onClick={() => set({ total_on: totalOn.filter((_, j) => j !== i) })}>削除</button>
                    </div>
                ))}
            </div>
        </div>
    );
}
