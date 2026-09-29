// src/components/DetailFrame/IdInput.jsx
// 語IDを数値で入力し，隣に綴りを表示する小さな入力欄．
export function IdInput({ value, onChange, words, placeholder = '' }) {
    return (
        <span className="idInput">
            <input
                className="textForm"
                type="number"
                placeholder={placeholder}
                value={value ?? ''}
                onChange={e => onChange(e.target.value === '' ? null : Number(e.target.value))}
            />
            <span className="idLabel">{value != null && words[value] ? words[value].entry : '（未指定）'}</span>
        </span>
    );
}
