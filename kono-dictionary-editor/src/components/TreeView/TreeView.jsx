import React from 'react';
import { useDictState, useDictDispatch } from '../../store/DictionaryContext';
import { isValidWordTag, ancestorList, hasNoCycle } from '../../utils/utils.js';
import { CATEGORY } from '../../constants/categories.js';
import { childStateCounts, coverState } from '../../domain/placement.js';
import './TreeView.scss';

/** 単一ノード */
const STATE_MARK = { 暫定配置: '~', 未配置: '·', 上位未決: '?' };
const STATE_CLASS = { 暫定配置: 'provisional', 未配置: 'unplaced', 上位未決: 'undecided' };

function WordItem({ id, parentId = null, editedIds, ancestorHighlights }) {
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

  const state = parentId === null ? '配置' : coverState(word, parentId).state;
  const counts = hasChildren ? childStateCounts(words, id) : null;
  const offTree = counts ? counts['未配置'] + counts['上位未決'] : 0;

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
          !isEdited && isAncestorOfEdited && 'editedAncestor',
          STATE_CLASS[state]
        ].filter(Boolean).join(' ')}
        title={state !== '配置' ? state : undefined}
        onClick={handleClick}
      >
        <span className="id">{id}</span>
        {STATE_MARK[state] && <span className="stateMark">{STATE_MARK[state]}</span>}
        <span className="entry">{word.entry}</span>
        {translation && <span className="translation">{translation}</span>}
        {offTree > 0 && <span className="offTreeCount" title="未配置・上位未決の子">+{offTree}</span>}
      </span>

      {isOpen && hasChildren && (
        <ul className="wordItemChildren">
          {children.map(childId => isValidWordTag(words, childId) ?
            <WordItem key={childId} id={childId} parentId={id} editedIds={editedIds} ancestorHighlights={ancestorHighlights} />
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
