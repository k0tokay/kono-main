// src/store/bundledDictionary.js
import initialData from '../data/konomeno-v5.json';

// 組み込み辞書の指紋。localStorage の保存内容がどの組み込み辞書を基にしたかを記録し、
// CLI などでソースJSONが更新されたときに古い保存内容が新しい辞書を隠さないようにする。
const fingerprint = (str) => {
    let h = 5381;
    for (let i = 0; i < str.length; i++) h = ((h * 33) ^ str.charCodeAt(i)) >>> 0;
    return `${str.length}:${h.toString(16)}`;
};

export const bundledWords = initialData.words;
export const BUNDLED_FINGERPRINT = fingerprint(JSON.stringify(initialData));
