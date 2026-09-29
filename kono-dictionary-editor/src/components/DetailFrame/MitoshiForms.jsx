// src/components/DetailFrame/MitoshiForms.jsx
// 見做し：見做し型の定義フォームと，語に当たる見做し語義（仮想・実体化済み）の一覧．
import { MITOSHI_CATEGORY, mitoshiTypes, sensesOf } from '../../domain/mitoshi.js';

const label = (words, id) => (id != null && words[id] ? `${id} ${words[id].entry}` : '—');

function IdInput({ value, onChange, words }) {
    return (
        <span className="idInput">
            <input
                className="textForm"
                type="number"
                value={value ?? ''}
                onChange={e => onChange(e.target.value === '' ? null : Number(e.target.value))}
            />
            <span className="idLabel">{value != null && words[value] ? words[value].entry : '（未指定）'}</span>
        </span>
    );
}

/** 見做しカテゴリの語：from / to / relation / uniform を編集する． */
export function MitoshiTypeForm({ word, words, edited, onChange }) {
    if (word.category !== MITOSHI_CATEGORY) return null;
    const t = word.mitoshi_type || { from: null, to: null, relation: null, uniform: false };
    const update = patch => onChange('mitoshi_type', { ...t, ...patch });
    return (
        <div className="largeListForm mitoshiTypeForm">
            <div className="formHeader listHeader">
                <label className={edited ? 'edited' : ''}>見做し型</label>
            </div>
            <div className="innerLargeListForm">
                <div className="mitoshiRow"><span>from</span><IdInput value={t.from} words={words} onChange={v => update({ from: v })} /></div>
                <div className="mitoshiRow"><span>to</span><IdInput value={t.to} words={words} onChange={v => update({ to: v })} /></div>
                <div className="mitoshiRow"><span>関係</span><IdInput value={t.relation} words={words} onChange={v => update({ relation: v })} /></div>
                <div className="mitoshiRow">
                    <label><input type="checkbox" checked={Boolean(t.uniform)} onChange={e => update({ uniform: e.target.checked })} />一様（from の下の全語に当てる）</label>
                </div>
            </div>
        </div>
    );
}

/** 普通の語：当たる見做し語義の一覧と，実体化・除外・個別の追加． */
export function MitoshiSenseForm({ word, words, edited, onChange, onMaterialize, onClick }) {
    if (word.category === MITOSHI_CATEGORY || word.category === 'カテゴリ') return null;
    const types = mitoshiTypes(words);
    if (types.length === 0) return null;
    const senses = sensesOf(words, word.id);
    const records = word.mitoshi_senses || [];
    const setRecords = next => onChange('mitoshi_senses', next);
    const excluded = records.filter(r => r.exclude);
    const addable = types.filter(t => !t.mitoshi_type?.uniform && !records.some(r => r.type === t.id));

    return (
        <div className="largeListForm mitoshiSenseForm">
            <div className="formHeader listHeader">
                <label className={edited ? 'edited' : ''}>見做し</label>
                {addable.length > 0 && (
                    <select value="" onChange={e => e.target.value && setRecords([...records, { type: Number(e.target.value), target: null, exclude: false }])}>
                        <option value="">個別に当てる…</option>
                        {addable.map(t => <option key={t.id} value={t.id}>{t.entry}</option>)}
                    </select>
                )}
            </div>
            <div className="innerLargeListForm">
                {senses.map(sense => (
                    <div key={sense.type} className="mitoshiRow">
                        <span className="typeEntry" onClick={() => onClick(sense.type)}>{sense.type_entry}</span>
                        <span>→ {label(words, sense.to)}</span>
                        {sense.target === null ? (
                            <>
                                <span className="virtual">仮想</span>
                                <button onClick={() => onMaterialize(sense.type)}>実体化</button>
                            </>
                        ) : (
                            <span className="target" onClick={() => onClick(sense.target)}>実体 {label(words, sense.target)}</span>
                        )}
                        {sense.uniform && sense.target === null && (
                            <button onClick={() => setRecords([...records.filter(r => r.type !== sense.type), { type: sense.type, target: null, exclude: true }])}>除外</button>
                        )}
                        {!sense.uniform && sense.target === null && (
                            <button onClick={() => setRecords(records.filter(r => r.type !== sense.type))}>外す</button>
                        )}
                    </div>
                ))}
                {excluded.map(r => (
                    <div key={`x${r.type}`} className="mitoshiRow excluded">
                        <span className="typeEntry">{words[r.type]?.entry}</span>
                        <span>除外中</span>
                        <button onClick={() => setRecords(records.filter(x => x.type !== r.type))}>戻す</button>
                    </div>
                ))}
                {senses.length === 0 && excluded.length === 0 && <div className="empty">当たる見做しはありません</div>}
            </div>
        </div>
    );
}
