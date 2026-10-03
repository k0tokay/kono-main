import React, { useState } from 'react';
import { useDictState, useDictDispatch } from '../../store/DictionaryContext';
import { isValidWordTag, ancestorList, hasNoCycle } from '../../utils/utils.js';
import { CATEGORY } from '../../constants/categories.js';
import { childStateCounts, coverState, isDisjoint } from '../../domain/placement.js';
import { membersOf } from '../../domain/kinds.js';
import './TreeView.scss';

/** 単一ノード */
/**
 * 子を分割ごとにまとめる（本文の図の「枠のない中間節点」に当たる）．
 * 宣言順に分割の群を並べ，どの分割にも参加しない子を最後に置く．
 * 子が一つもない分割も見出しだけ出す（宣言したが枝がまだない）．
 */
function groupChildren(words, word) {
  const children = (word.lower_covers || []).filter(childId => isValidWordTag(words, childId));
  const partitions = word.partitions || [];
  if (partitions.length === 0) return [{ partition: null, children }];
  const byKey = new Map(partitions.map(p => [p.key, []]));
  const rest = [];
  for (const childId of children) {
    const key = coverState(words[childId], word.id).partition;
    if (key != null && byKey.has(key)) byKey.get(key).push(childId);
    else rest.push(childId);
  }
  return [
    ...partitions.map(p => ({ partition: p, children: byKey.get(p.key) })),
    { partition: null, children: rest },
  ];
}

/**
 * 種の節点の下に所属する成員をまとめて出す（被覆辺＝包摂とは分けて表示する）．
 * 成員は保存されていない：シグネチャと dent から計算．引用 ⌜a⌝ は仮想の節点．
 */
function MemberGroup({ members }) {
  const { words, focusId } = useDictState();
  const dispatch = useDictDispatch();
  const [open, setOpen] = useState(false);
  return (
    <li className="memberGroup">
      <span className={['wordItemMain', 'hasChildren', open && 'open'].filter(Boolean).join(' ')} onClick={() => setOpen(o => !o)}>
        <span className="memberLabel">∋ 成員</span>
        <span className="offTreeCount">{members.length}</span>
      </span>
      {open && (
        <ul className="memberChildren">
          {members.map(m => (
            <li key={`${m.show}:${m.id}`}>
              <span
                className={['wordItemMain', m.show === 'quote' ? 'quoteItem' : 'memberItem', focusId === m.id && 'focus'].filter(Boolean).join(' ')}
                title={m.source === 'signature' ? 'シグネチャから' : 'dent で登録'}
                onClick={() => dispatch({ type: 'SET_FOCUS', payload: m.id })}
              >
                <span className="id">{m.id}</span>
                <span className="entry">{m.show === 'quote' ? `⌜${words[m.id].entry}⌝` : words[m.id].entry}</span>
                {m.source === 'fact' && <span className="sourceMark">登録</span>}
                {m.show === 'quote' && (
                  <button className="materializeBtn" onClick={e => { e.stopPropagation(); dispatch({ type: 'MATERIALIZE_QUOTE', payload: { id: m.id } }); }}>実体化</button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

const STATE_MARK = { 上位未決: '?' };
const STATE_CLASS = { 上位未決: 'undecided' };

function WordItem({ id, parentId = null, editedIds, ancestorHighlights }) {
  const { words, openSet, focusId } = useDictState();
  const dispatch = useDictDispatch();
  const word = words[id];
  const children = word.lower_covers || [];
  const isOpen = openSet.has(id);
  const members = membersOf(words, id);
  const hasChildren = children.length > 0 || members.length > 0;

  const isEdited = editedIds.has(id);
  const isAncestorOfEdited = ancestorHighlights.has(id);

  const handleClick = () => {
    dispatch({ type: 'TOGGLE_OPEN', payload: id });
    dispatch({ type: 'SET_FOCUS', payload: id });
  };

  const state = parentId === null ? '配置' : coverState(word, parentId).state;
  const counts = children.length > 0 ? childStateCounts(words, id) : null;
  const offTree = counts ? counts['上位未決'] : 0;

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
          STATE_CLASS[state],
          word.is_function && 'isFunction'
        ].filter(Boolean).join(' ')}
        title={state !== '配置' ? state : undefined}
        onClick={handleClick}
      >
        <span className="id">{id}</span>
        {STATE_MARK[state] && <span className="stateMark">{STATE_MARK[state]}</span>}
        {word.is_function && <span className="funcMark" title="関数">ƒ</span>}
        <span className="entry">{word.entry}</span>
        {translation && <span className="translation">{translation}</span>}
        {offTree > 0 && <span className="offTreeCount" title="上位未決の子">+{offTree}</span>}
      </span>

      {isOpen && hasChildren && (
        <ul className="wordItemChildren">
          {groupChildren(words, word).map(group => group.partition ? (
            <li key={`p:${group.partition.key}`} className="partitionGroup">
              <span className="partitionLabel" title={group.partition.note || undefined}>
                {group.partition.key}
                <span className="partitionFlags">
                  {[group.partition.kind, isDisjoint(group.partition) ? '排他' : '非排他', group.partition.exhaustive && '網羅'].filter(Boolean).join('・')}
                </span>
              </span>
              <ul className="partitionChildren">
                {group.children.map(childId => (
                  <WordItem key={childId} id={childId} parentId={id} editedIds={editedIds} ancestorHighlights={ancestorHighlights} />
                ))}
              </ul>
            </li>
          ) : group.children.map(childId => (
            <WordItem key={childId} id={childId} parentId={id} editedIds={editedIds} ancestorHighlights={ancestorHighlights} />
          )))}
          {members.length > 0 && <MemberGroup members={members} />}
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

  // 表示の起点：display_root の語（無ければ従来どおりカテゴリの語）
  const flagged = words.filter(w => w && w.display_root === true).map(w => w.id);
  const roots = flagged.length > 0
    ? flagged
    : words.filter(w => w && w.category === CATEGORY.ROOT).map(w => w.id);

  return (
    <div className="wordTree">
      <ul>
        {roots.map(id => <WordItem key={id} id={id} editedIds={editedIds} ancestorHighlights={ancestorHighlights} />)}
      </ul>
    </div>
  );
}
