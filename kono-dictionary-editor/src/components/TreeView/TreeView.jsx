import React from 'react';
import { useDictState, useDictDispatch } from '../../store/DictionaryContext';
import { isValidWordTag, ancestorList, hasNoCycle } from '../../utils/utils.js';
import { CATEGORY } from '../../constants/categories.js';
import './TreeView.scss';

/** 単一ノード */
function WordItem({ id, editedIds, ancestorHighlights }) {
  const { words, openSet, focusId } = useDictState();
  const dispatch = useDictDispatch();
  const word = words[id];
  const children = word.lower_covers || [];
  const isOpen = openSet.has(id);
  const hasChildren = children.length > 0;

  const isEdited = editedIds.has(id);
  const isAncestorOfEdited = ancestorHighlights.has(id);

  const handleClick = () => {
    dispatch({ type: 'TOGGLE_OPEN', payload: id });
    dispatch({ type: 'SET_FOCUS', payload: id });
  };

  const translation = word.translations?.length > 0
    ? word.translations.slice(0, 3).join(', ')
    : '';

  return (
    <li>
      <span
        className={[
          'wordItemMain',
          isOpen && 'open',
          hasChildren && 'hasChildren',
          focusId === id && 'focus',
          isEdited && 'edited',
          !isEdited && isAncestorOfEdited && 'editedAncestor'
        ].filter(Boolean).join(' ')}
        onClick={handleClick}
      >
        <span className="id">{id}</span>
        <span className="entry">{word.entry}</span>
        {translation && <span className="translation">{translation}</span>}
      </span>

      {isOpen && hasChildren && (
        <ul className="wordItemChildren">
          {children.map(childId => isValidWordTag(words, childId) ?
            <WordItem key={childId} id={childId} editedIds={editedIds} ancestorHighlights={ancestorHighlights} />
            : null
          )}
        </ul>
      )}
    </li>
  );
}

/** カテゴリルート配下を表示 */
export function WordTree() {
  const { words, editedFields } = useDictState();
  if (!hasNoCycle({ words }, true)) {
    return null;
  }

  const editedIds = new Set(editedFields.keys());
  const ancestorHighlights = new Set();
  editedIds.forEach(eid => {
    if (words[eid]) {
      ancestorList(words, eid).forEach(aid => ancestorHighlights.add(aid));
    }
  });

  const roots = words
    .map((w, i) => (w && w.category === CATEGORY.ROOT ? i : -1))
    .filter(i => i !== -1);

  return (
    <div className="wordTree">
      <ul>
        {roots.map(id => <WordItem key={id} id={id} editedIds={editedIds} ancestorHighlights={ancestorHighlights} />)}
      </ul>
    </div>
  );
}
