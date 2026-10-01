import { useDictState, useDictDispatch } from '../store/DictionaryContext';
import { useState, useRef, useEffect } from 'react';
import { isValidWordTag } from '../utils/utils.js';
import React from 'react';

const punctuations = ['，', ',', '、'];
const splitPunc = (text) =>
    text.split(new RegExp(`[${punctuations.join('')}]`))
        .map(x => x.trim()); //.filter(x => x !== "") をつけると編集時に最後に,がつけられない

export function BasicForm({ name, title, value, edited, onChange,
    isReadOnly = false, isList = false, isMultiline = false, buttons = [] }) {
    const handleChange = (e) => {
        const raw = e.target.value;
        const data = isList ? splitPunc(raw) : raw;
        onChange(name, data);
    };
    return (
        <div className="basicForm">
            <div className="formHeader basicHeader">
                <label className={edited ? "edited" : ""}>{title}</label>
                {buttons.map((btn, i) =>
                    <button key={i} onClick={btn.onClick}>{btn.label}</button>
                )}
            </div>
            {isMultiline ? (
                <textarea
                    className="textForm"
                    rows="3"
                    value={value}
                    onChange={handleChange}
                    readOnly={isReadOnly}
                />
            ) : (
                <input
                    className="textForm"
                    type="text"
                    value={value}
                    onChange={handleChange}
                    readOnly={isReadOnly}
                />
            )}
        </div>
    );
}

export function TagWordDetails({ word, onClick }) {
    return (
        <div className="tagWordDetails">
            <div className="innerTagWordDetails" onClick={onClick}>
                <span className="id">{word.id}</span>
                <span className="entry">{word.entry}</span>
                {word.translations?.length > 0 && (
                    <span className="translations">{word.translations.slice(0, 2).join(', ')}</span>
                )}
            </div>
        </div>
    );
}

function WordSuggestions({ query, words, onSelect, visible }) {
    if (!visible || !query) return null;

    const matches = [];
    for (let i = 0; i < words.length; i++) {
        const w = words[i];
        if (!w) continue;
        if (w.entry.includes(query) || String(w.id).startsWith(query)) {
            matches.push(w);
        }
        if (matches.length >= 8) break;
    }
    if (matches.length === 0) return null;

    return (
        <div className="wordSuggestions">
            {matches.map(w => (
                <div key={w.id} className="suggestionItem"
                    onMouseDown={(e) => { e.preventDefault(); onSelect(w.id); }}>
                    <span className="id">{w.id}</span>
                    <span className="entry">{w.entry}</span>
                    {w.translations?.length > 0 && (
                        <span className="translations">{w.translations.slice(0, 2).join(', ')}</span>
                    )}
                </div>
            ))}
        </div>
    );
}

export function TagForm({ name, title, tags, wordId, onChange, onClick, edited,
    isWord = false, isReadOnly = false,
}) {
    const { words } = useDictState();
    const dispatch = useDictDispatch();
    const [editingIndex, setEditingIndex] = useState(null);
    const [inputText, setInputText] = useState('');

    const tagList = tags;

    const displayToRaw = (text) => !isWord || !isValidWordTag(words, text) ? text : Number(text);
    const displayToRawList = (textList) => textList.map(t => displayToRaw(t));

    const displayTag = (tag, i) => {
        if (isWord && words[tag] && i !== editingIndex) {
            return words[tag].entry;
        } else if (i === editingIndex) {
            return inputText;
        } else {
            return tag;
        }
    };

    const resolveEntry = (text) => {
        if (isValidWordTag(words, text)) return Number(text);
        for (let i = 0; i < words.length; i++) {
            if (words[i] && words[i].entry === text) return i;
        }
        return text;
    };

    const handleSelectSuggestion = (selectedId) => {
        if (editingIndex === null) return;
        const newTags = tagList.map((t, j) => j === editingIndex ? selectedId : t);
        onChange(name, newTags);
        setInputText(words[selectedId].entry);

        if (isWord && (name === 'upper_covers' || name === 'lower_covers')) {
            setTimeout(() => {
                dispatch({ type: "UPDATE_COVERS", payload: { id: wordId, field: name, tag: selectedId } });
                setEditingIndex(null);
                setInputText('');
            }, 0);
        } else {
            setEditingIndex(null);
            setInputText('');
        }
    };

    const handleBlur = () => {
        if (editingIndex === null) return;
        if (isWord && (name === 'upper_covers' || name === 'lower_covers')) {
            const resolved = resolveEntry(inputText);
            if (resolved !== inputText) {
                const newTags = tagList.map((t, j) => j === editingIndex ? resolved : t);
                onChange(name, newTags);
                dispatch({ type: "UPDATE_COVERS", payload: { id: wordId, field: name, tag: resolved } });
            } else {
                const tag = tagList[editingIndex];
                dispatch({ type: "UPDATE_COVERS", payload: { id: wordId, field: name, tag } });
            }
        } else if (isWord) {
            const resolved = resolveEntry(inputText);
            const newTags = tagList.map((t, j) => j === editingIndex ? resolved : t).filter(t => t !== "");
            onChange(name, newTags);
        } else {
            const newTags = tagList.filter(t => t !== "");
            onChange(name, displayToRawList(newTags));
        }
        setEditingIndex(null);
        setInputText('');
    };

    const addTag = () => {
        const newTags = [...tagList, ""];
        onChange(name, displayToRawList(newTags));
    };

    return (
        <div className="tagForm">
            <div className="formHeader tagHeader">
                <p className={edited ? "edited" : ""}>{title}</p>
                {!isReadOnly && <button onClick={addTag}>追加</button>}
            </div>
            <div className="textForm innerTagForm">
                {tagList.map((tag, i) => (
                    <div key={i} style={{ position: 'relative' }}>
                        {isWord && words[tag] && i !== editingIndex && (
                            <TagWordDetails word={words[tag]} onClick={() => onClick(tag)} />
                        )}
                        <input
                            type="text"
                            className={`tagInput ${isWord && i !== editingIndex && !isValidWordTag(words, tag) ? "notValid" : ""}`}
                            value={displayTag(tag, i)}
                            readOnly={isReadOnly}
                            onFocus={() => {
                                setEditingIndex(i);
                                setInputText(isWord && words[tag] ? words[tag].entry : String(tag));
                            }}
                            onChange={e => {
                                const val = e.target.value;
                                setInputText(val);
                                if (!isWord) {
                                    const newTags = tagList.map((t, j) =>
                                        j === i ? val : t
                                    );
                                    onChange(name, displayToRawList(newTags));
                                } else {
                                    const resolved = resolveEntry(val);
                                    const newTags = tagList.map((t, j) =>
                                        j === i ? resolved : t
                                    );
                                    onChange(name, newTags);
                                }
                            }}
                            onBlur={handleBlur}
                        />
                        {isWord && i === editingIndex && (
                            <WordSuggestions
                                query={inputText}
                                words={words}
                                onSelect={handleSelectSuggestion}
                                visible={editingIndex === i}
                            />
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}

export function LargeListForm({ name, title, title_h, title_c, contents, edited, onChange }) {
    const addItem = () => {
        const updated = [...contents, { title: "", text: "" }];
        onChange(name, updated);
    };
    const deleteItem = (idx) => {
        const updated = contents.filter((_, i) => i !== idx);
        onChange(name, updated);
    };
    const updateItem = (idx) => (_field, val) => {
        const updated = contents.slice();
        updated[idx] = val;
        onChange(name, updated);
    };

    return (
        <div className="largeListForm">
            <div className="formHeader listHeader">
                <p className={edited ? "edited" : ""}>{title}</p>
                <button onClick={addItem}>追加</button>
            </div>
            <div className="innerLargeListForm">
                {contents.map((content, i) => (
                    <div key={i} className="largeListItem">
                        <div className="largeListItemHeader">
                            <input
                                className="lineInput itemTitle"
                                type="text"
                                placeholder={title_h}
                                value={content.title}
                                onChange={e => updateItem(i)(name, { ...content, title: e.target.value })}
                            />
                            <button className="deleteItemBtn" onClick={() => deleteItem(i)}>削除</button>
                        </div>
                        <textarea
                            className="lineInput"
                            rows="3"
                            placeholder={title_c}
                            value={content.text}
                            onChange={e => updateItem(i)(name, { ...content, text: e.target.value })}
                        />
                    </div>
                ))}
            </div>
        </div>
    );
}

export function RelationForm({ name, title, relations, edited, onChange, onClick }) {
    const { words } = useDictState();
    const [editingIdx, setEditingIdx] = useState(null);
    const [inputText, setInputText] = useState('');

    const addItem = () => {
        onChange(name, [...relations, { title: "", entry: "" }]);
    };
    const deleteItem = (idx) => {
        onChange(name, relations.filter((_, i) => i !== idx));
    };
    const updateTitle = (idx, val) => {
        const updated = relations.slice();
        updated[idx] = { ...updated[idx], title: val };
        onChange(name, updated);
    };

    const resolveEntry = (text) => {
        if (isValidWordTag(words, text)) return Number(text);
        for (let i = 0; i < words.length; i++) {
            if (words[i] && words[i].entry === text) return i;
        }
        return text;
    };

    const handleSelectSuggestion = (idx, selectedId) => {
        const updated = relations.slice();
        updated[idx] = { ...updated[idx], entry: selectedId };
        onChange(name, updated);
        setInputText(words[selectedId].entry);
        setEditingIdx(null);
    };

    const handleBlur = (idx) => {
        const resolved = resolveEntry(inputText);
        const updated = relations.slice();
        updated[idx] = { ...updated[idx], entry: resolved };
        onChange(name, updated);
        setEditingIdx(null);
        setInputText('');
    };

    const displayEntry = (rel, idx) => {
        if (idx === editingIdx) return inputText;
        if (words[rel.entry]) return words[rel.entry].entry;
        return String(rel.entry);
    };

    return (
        <div className="largeListForm">
            <div className="formHeader listHeader">
                <p className={edited ? "edited" : ""}>{title}</p>
                <button onClick={addItem}>追加</button>
            </div>
            <div className="innerLargeListForm">
                {relations.map((rel, i) => (
                    <div key={i} className="largeListItem">
                        <div className="largeListItemHeader">
                            <input
                                className="lineInput itemTitle"
                                type="text"
                                placeholder="分類"
                                value={rel.title}
                                onChange={e => updateTitle(i, e.target.value)}
                            />
                            <button className="deleteItemBtn" onClick={() => deleteItem(i)}>削除</button>
                        </div>
                        <div className="tagForm relationTarget">
                            <div className="innerTagForm">
                                <div style={{ position: 'relative' }}>
                                    {words[rel.entry] && i !== editingIdx && (
                                        <TagWordDetails word={words[rel.entry]} onClick={() => onClick(rel.entry)} />
                                    )}
                                    <input
                                        type="text"
                                        className={`tagInput ${i !== editingIdx && !isValidWordTag(words, rel.entry) && rel.entry !== "" ? "notValid" : ""}`}
                                        value={displayEntry(rel, i)}
                                        onFocus={() => {
                                            setEditingIdx(i);
                                            setInputText(words[rel.entry] ? words[rel.entry].entry : String(rel.entry));
                                        }}
                                        onChange={e => setInputText(e.target.value)}
                                        onBlur={() => handleBlur(i)}
                                    />
                                    {i === editingIdx && (
                                        <WordSuggestions
                                            query={inputText}
                                            words={words}
                                            onSelect={(id) => handleSelectSuggestion(i, id)}
                                            visible={editingIdx === i}
                                        />
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

export function MenuBar({ items }) {
    return (
        <div className="menuBar">
            {items.map((it, i) => (
                <button key={i} onClick={it.onClick} title={it.shortcut ? `${it.title} (${it.shortcut})` : undefined}>
                    {it.title}
                </button>
            ))}
        </div>
    );
}

// 純粋なUIコンポーネント。ドメインロジックは呼び出し元で行うこと
export function CheckboxForm({ name, title, checked = false, onChange, disabled = false }) {
    const handleChange = (e) => {
        onChange(name, e.target.checked);
    };

    return (
        <div className="checkboxForm">
            <label htmlFor={name} className="formHeader checkboxHeader">
                <span>{title}</span>
                <input
                    type="checkbox"
                    id={name}
                    name={name}
                    checked={checked}
                    onChange={handleChange}
                    disabled={disabled}
                />
            </label>
        </div>
    );
}
