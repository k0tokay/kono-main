// src/store/DictionaryContext.jsx
import { createContext, useReducer, useContext } from 'react';
import { bundledWords, BUNDLED_FINGERPRINT } from './bundledDictionary.js';
import { createBlankWord, checkIntegrity, hasNoCycle } from '../utils/utils.js';
import { deleteWordInPlace } from '../domain/dictionaryCore.js';
import { applyDerivedSequenceCovers, isSequenceWord } from '../domain/soundSequences.js';
import { ancestorList, isValidWordTag } from '../utils/utils.js';
import { CATEGORY } from '../constants/categories.js';

const DictionaryStateCtx = createContext();
const DictionaryDispatchCtx = createContext();

const getFirstRootId = (words) => {
    for (let i = 0; i < words.length; i++) {
        if (words[i] && words[i].category === CATEGORY.ROOT) {
            return i;
        }
    }
    return 0;
};

function markEdited(editedFields, id, field) {
    const next = new Map(editedFields);
    const fields = new Set(next.get(id) || []);
    fields.add(field);
    next.set(id, fields);
    return next;
}

function dictionaryReducer(state, action) {
    switch (action.type) {
        case 'UPDATE_FIELD': {
            return updateField(state, action.payload);
        }
        case "UPDATE_COVERS": {
            return updateCovers(state, action.payload);
        }
        case 'ADD_WORD': {
            return addWord(state, action.payload);
        }
        case 'DELETE_WORD': {
            return deleteWord(state, action.payload);
        }
        case 'TOGGLE_OPEN': {
            const set = new Set(state.openSet);
            if (state.focusId !== action.payload) return state;
            if (set.has(action.payload)) set.delete(action.payload);
            else set.add(action.payload);
            return { ...state, openSet: set };
        }
        case 'OPEN_WORD': {
            const id = action.payload;
            const set = new Set(state.openSet);
            ancestorList(state.words, id).forEach(aid => {
                set.add(aid);
            });
            return { ...state, openSet: set };
        }
        case 'SET_FOCUS': {
            return { ...state, focusId: action.payload };
        }
        case 'SET_DICTIONARY': {
            const words = action.payload.words;
            return { ...state, words, openSet: new Set(), focusId: getFirstRootId(words), editedFields: new Map() };
        }
        case 'CLEAR_EDITED': {
            return { ...state, editedFields: new Map() };
        }
        default:
            throw new Error(`Unknown action: ${action.type}`);
    }
}

export function DictionaryProvider({ children }) {
    let initialWords = bundledWords;
    if (typeof window !== 'undefined') {
        try {
            const stored = localStorage.getItem('dictionary');
            if (stored) {
                const parsed = JSON.parse(stored);
                if (parsed.words && parsed.base === BUNDLED_FINGERPRINT) {
                    initialWords = parsed.words;
                } else if (parsed.words) {
                    localStorage.setItem('dictionary.stale', stored);
                    localStorage.removeItem('dictionary');
                    console.warn('組み込み辞書が更新されたため localStorage の保存内容を破棄しました（dictionary.stale に退避）');
                }
            }
        } catch {
            // ignore parse error and fall back to bundled data
        }
    }

    const [state, dispatch] = useReducer(dictionaryReducer, {
        words: initialWords,
        openSet: new Set(),
        focusId: getFirstRootId(initialWords),
        editedFields: new Map(),
    });
    return (
        <DictionaryStateCtx.Provider value={state}>
            <DictionaryDispatchCtx.Provider value={dispatch}>
                {children}
            </DictionaryDispatchCtx.Provider>
        </DictionaryStateCtx.Provider>
    );
}

export const useDictState = () => useContext(DictionaryStateCtx);
export const useDictDispatch = () => useContext(DictionaryDispatchCtx);


function updateField(state, { id, field, value }) {
    const word = state.words[id];
    if (!word) return state;

    const newWords = structuredClone(state.words);
    newWords[id] = {
        ...word,
        [field]: value
    };

    let editedFields = markEdited(state.editedFields, id, field);
    if (field === 'entry' && isSequenceWord(word)) {
        // 音列の綴りが変われば，それを含む音列・含まれる音列の被覆も変わる
        for (const changedId of applyDerivedSequenceCovers(newWords)) {
            editedFields = markEdited(editedFields, changedId, 'upper_covers');
        }
    }
    return { ...state, words: newWords, editedFields };
}

// payload: { id, field, tag }
// tag: blur時点で編集していたタグの値（数値IDまたは空文字列など）
function updateCovers(state, { id, field, tag }) {
    const word = state.words[id];
    if (!word) return state;

    const invField = field === 'upper_covers' ? 'lower_covers' : 'upper_covers';
    const target = isValidWordTag(state.words, tag) ? state.words[Number(tag)] : null;
    if (isSequenceWord(word) || isSequenceWord(target)) {
        // 音列の被覆は綴りから導出する．手での編集は受け付けない
        return state;
    }

    const newWords = structuredClone(state.words);

    // 空・無効エントリを除去
    newWords[id][field] = newWords[id][field].filter(
        t => t !== "" && t !== null && isValidWordTag(state.words, t)
    );

    // 逆リンクの整合：field から消えた相手側の invField から id を除去
    for (const w of newWords) {
        if (!w) continue;
        for (const t of w[invField]) {
            if (t === id && !newWords[id][field].includes(w.id)) {
                w[invField] = w[invField].filter(tid => tid !== id);
            }
        }
    }

    // 新しいタグが有効なら逆リンクを追加
    if (!isValidWordTag(state.words, tag)) {
        return { ...state, words: newWords };
    }

    const numTag = Number(tag);
    if (!newWords[numTag]) return { ...state, words: newWords };
    // すでにリンク済みなら追加しない（重複防止）
    if (!newWords[numTag][invField].includes(id)) {
        newWords[numTag] = {
            ...newWords[numTag],
            [invField]: [...newWords[numTag][invField], id]
        };
    }

    if (hasNoCycle({ words: newWords })) {
        checkIntegrity({ words: newWords });
        return { ...state, words: newWords, editedFields: markEdited(state.editedFields, id, field) };
    } else {
        newWords[numTag][invField] = newWords[numTag][invField].filter(t => t !== id);
        newWords[id][field] = newWords[id][field].filter(t => t !== numTag);
        return { ...state, words: newWords };
    }
}

function addWord(state, parentId) {
    const parent = state.words[parentId];
    if (!parent) return state;

    const category = parent.category === CATEGORY.ROOT ? parent.entry : parent.category; // 親のカテゴリを引き継ぐ(親がカテゴリの場合は例外処理)
    const newWord = createBlankWord(parentId, category, state.words.length);
    const words = [...state.words, newWord];
    // 親のlower_coversに新しい単語を追加
    words[parentId] = {
        ...parent,
        lower_covers: [...parent.lower_covers, newWord.id]
    };

    checkIntegrity({ words });
    applyDerivedSequenceCovers(words);
    const ef = markEdited(state.editedFields, newWord.id, '_new');
    return { ...state, words, focusId: newWord.id, editedFields: markEdited(ef, parentId, 'lower_covers') };
}

function deleteWord(state, { id }) {
    const victim = state.words[id];
    if (!victim) return state;
    const words = structuredClone(state.words);
    deleteWordInPlace(words, {
        id,
        expect: { entry: victim.entry },
        reconnect: 'parents',
        reference_policy: 'remove',
    });
    const newFocus = victim.upper_covers.find(parentId => words[parentId]) ?? getFirstRootId(words);

    checkIntegrity({ words });
    applyDerivedSequenceCovers(words);

    let ef = markEdited(state.editedFields, id, '_deleted');
    for (let wordId = 0; wordId < words.length; wordId++) {
        if (wordId !== id && JSON.stringify(words[wordId]) !== JSON.stringify(state.words[wordId])) {
            ef = markEdited(ef, wordId, '_delete_cleanup');
        }
    }
    return { ...state, words, focusId: newFocus, editedFields: ef };
}
