// src/components/OtherFrames/OtherFrames.jsx

import React, { useState } from 'react';
import { useDictState, useDictDispatch } from '../../store/DictionaryContext';
import { search } from '../../utils/utils.js';
import { BasicForm } from '../CommonForms';
import './OtherFrames.scss';

function SearchResultTag({ word, onSelect }) {
  return (
    <div className="searchResultTag" onClick={() => onSelect(word.id)}>
      <span className="id">{word.id}</span>
      <span className="entry">{word.entry}</span>
      <span className="translations">{word.translations?.join('，')}</span>
    </div>
  );
}

export function SearchFrame() {
  const { words, openSet } = useDictState();
  const dispatch = useDictDispatch();

  const [idQuery, setIdQuery] = useState("");
  const [entryQuery, setEntryQuery] = useState("");
  const [transQuery, setTransQuery] = useState("");

  const notEmpty = idQuery || entryQuery || transQuery;
  const results = notEmpty
    ? search(
      { words },
      idQuery ? Number(idQuery) : null,
      entryQuery ? entryQuery : null,
      transQuery ? transQuery : null
    )
    : [];

  const handleSelect = (id) => {
    dispatch({ type: 'OPEN_WORD', payload: id });
    dispatch({ type: 'SET_FOCUS', payload: id });
  };

  return (
    <div className="searchFrameContainer">
      <div className="searchFormContainer">
        <BasicForm
          name="id"
          title="ID"
          value={idQuery}
          onChange={(f, v) => setIdQuery(v)}
        />
        <BasicForm
          name="entry"
          title="綴り"
          value={entryQuery}
          onChange={(f, v) => setEntryQuery(v)}
        />
        <BasicForm
          name="translations"
          title="翻訳"
          value={transQuery}
          isMultiline
          onChange={(f, v) => setTransQuery(v)}
        />
      </div>
      <div className="searchResultContainer">
        <span className="formHeader">検索結果</span>
        <div className="searchResult">
          {results.map((w, i) => (
            <SearchResultTag key={i} word={w} onSelect={handleSelect} />
          ))}
        </div>
      </div>
    </div>
  );
}

export function EmptyFrame() {
  return <div className="emptyFrame">∅</div>;
}
