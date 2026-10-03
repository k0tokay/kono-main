// src/components/DetailFrame/KindsForm.jsx
// 種：語が属する種（シグネチャから生成されるもの＋dent で登録したもの），種の語の生成規則（generator）．
import { kindsOf, membersOf, signatureOf } from '../../domain/kinds.js';
import { IdInput } from './IdInput';

const label = (words, id) => (id != null && words[id] ? `${id} ${words[id].entry}` : '—');
const SOURCE_LABEL = { signature: 'シグネチャから', fact: '登録' };

/** 語が属する種．dent（属性のない種への所属）を編集する． */
export function KindsForm({ word, words, edited, onChange, onClick }) {
    const dent = word.dent || [];
    const set = next => onChange('dent', next.length ? next : undefined);
    const derived = kindsOf(words, word.id).filter(k => k.source !== 'fact');
    const sig = signatureOf(word);
    return (
        <div className="largeListForm kindsForm">
            <div className="formHeader listHeader">
                <label className={edited ? 'edited' : ''}>所属（∈）</label>
                <button onClick={() => set([...dent, null])}>追加</button>
            </div>
            <div className="innerLargeListForm">
                <div className="largeListItemHeader kindNote">
                    <span className="muted">{sig ? `シグネチャ：tArity=${sig.tArity}，${sig.isFunc ? '関数' : '述語'}` : 'シグネチャ未設定（関数性か引数が未入力）'}</span>
                    {word.quote_of != null && (
                        <span className="link" onClick={() => onClick(word.quote_of)}>⌜{label(words, word.quote_of)}⌝ の実体</span>
                    )}
                </div>
                {derived.map((k, i) => (
                    <div key={`d${i}`} className="largeListItemHeader">
                        <span className="link" onClick={() => onClick(k.kind)}>{label(words, k.kind)}</span>
                        <span className="muted">{SOURCE_LABEL[k.source]}</span>
                    </div>
                ))}
                {dent.map((k, i) => (
                    <div key={`f${i}`} className="largeListItemHeader">
                        <IdInput value={k} words={words} placeholder="種" onChange={v => set(dent.map((x, j) => (j === i ? v : x)))} />
                        <button className="deleteItemBtn" onClick={() => set(dent.filter((_, j) => j !== i))}>削除</button>
                    </div>
                ))}
            </div>
        </div>
    );
}

/** 種の語：シグネチャによる成員の生成． */
export function GeneratorForm({ word, words, edited, onChange }) {
    const g = word.generator;
    const set = next => onChange('generator', next ?? undefined);
    const count = membersOf(words, word.id).length;
    return (
        <div className="largeListForm generatorForm">
            <div className="formHeader listHeader">
                <label className={edited ? 'edited' : ''}>成員の生成</label>
                <span className="muted">成員 {count}</span>
            </div>
            <div className="innerLargeListForm">
                <div className="largeListItemHeader">
                    <label><input type="checkbox" checked={Boolean(g)} onChange={e => set(e.target.checked ? { tArity: 1, isFunc: false } : null)} />シグネチャで生成</label>
                    {g && (
                        <>
                            <span className="muted">tArity</span>
                            <input className="lineInput tArityInput" type="number" min="0" value={g.tArity} onChange={e => set({ ...g, tArity: Math.max(0, Number(e.target.value) || 0) })} />
                            <label><input type="checkbox" checked={g.isFunc} onChange={e => set({ ...g, isFunc: e.target.checked })} />関数</label>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
