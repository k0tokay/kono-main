// src/components/DetailFrame/DetailFrame.jsx
import { useMemo } from 'react';
import { useDictState, useDictDispatch } from '../../store/DictionaryContext';
import { BasicForm, TagForm, LargeListForm, RelationForm, MenuBar, CheckboxForm } from '../CommonForms';
import { CoverStateForm, PartitionForm } from './PlacementForms';
import { MitoshiSenseForm, MitoshiTypeForm } from './MitoshiForms';
import './DetailFrame.scss';

// ──────────────────────────────────────────
// DetailFrame 本体
// ──────────────────────────────────────────

export default function DetailFrame() {
  const { words, focusId, editedFields } = useDictState();
  const dispatch = useDictDispatch();
  const word = words[focusId];
  if (!word) return null;
  const editedSet = editedFields.get(focusId) || new Set();

  // フィールド更新
  const handleChange = (field, value) => {
    dispatch({ type: 'UPDATE_FIELD', payload: { id: focusId, field, value } });
  };

  // is_function は下位語があるとtrueにできないためドメインチェックをここで行う
  const handleIsFunctionChange = (field, value) => {
    if (value && word.lower_covers.length > 0) {
      alert("下位語がある場合はチェックできません"); // eslint-disable-line no-alert
      return;
    }
    dispatch({ type: 'UPDATE_FIELD', payload: { id: focusId, field, value } });
  };

  // 追加／削除はすべて context reducer へ
  const handleAdd = () => {
    dispatch({ type: 'ADD_WORD', payload: focusId });
    dispatch({ type: 'OPEN_WORD', payload: focusId });
  };
  const handleDelete = () => dispatch({ type: 'DELETE_WORD', payload: { id: focusId } });

  const usedAsArgBy = useMemo(() => {
    const result = [];
    for (let i = 0; i < words.length; i++) {
      if (!words[i] || !words[i].arguments) continue;
      if (words[i].arguments.includes(focusId)) {
        result.push(words[i]);
      }
    }
    return result;
  }, [words, focusId]);

  // 詳細メニューバー
  const menuItems = [
    { title: '追加', onClick: handleAdd },
    { title: '削除', onClick: handleDelete }
  ];

  return (
    <div className="renderInfo">
      <MenuBar items={menuItems} />
      <div className="infoContainer">
        <BasicForm name="id" title="ID" value={word.id} isReadOnly />
        <BasicForm name="entry" title="綴り" value={word.entry} edited={editedSet.has('entry')} onChange={handleChange} />
        <BasicForm
          name="translations"
          title="翻訳"
          value={word.translations}
          edited={editedSet.has('translations')}
          isList
          isMultiline
          onChange={handleChange}
        />
        <TagForm
          key="arguments"
          wordId={focusId}
          name="arguments"
          title="引数"
          tags={word.arguments}
          edited={editedSet.has('arguments')}
          isWord
          onChange={handleChange}
          onClick={(id) => dispatch({ type: 'SET_FOCUS', payload: id })}
        />
        <TagForm
          key="upper_covers"
          wordId={focusId}
          name="upper_covers"
          title="上位語"
          tags={word.upper_covers}
          edited={editedSet.has('upper_covers')}
          isWord
          onChange={handleChange}
          onClick={(id) => dispatch({ type: 'SET_FOCUS', payload: id })}
        />
        <CoverStateForm
          word={word}
          words={words}
          edited={editedSet.has('cover_states')}
          onChange={handleChange}
          onClick={(id) => dispatch({ type: 'SET_FOCUS', payload: id })}
        />
        <TagForm
          key="lower_covers"
          wordId={focusId}
          name="lower_covers"
          title="下位語"
          tags={word.lower_covers}
          edited={editedSet.has('lower_covers')}
          isWord
          onChange={handleChange}
          onClick={(id) => dispatch({ type: 'SET_FOCUS', payload: id })}
        />
        <PartitionForm
          word={word}
          words={words}
          edited={editedSet.has('partitions')}
          onChange={handleChange}
        />
        <MitoshiTypeForm
          word={word}
          words={words}
          edited={editedSet.has('mitoshi_type')}
          onChange={handleChange}
        />
        <MitoshiSenseForm
          word={word}
          words={words}
          edited={editedSet.has('mitoshi_senses')}
          onChange={handleChange}
          onMaterialize={(type) => dispatch({ type: 'MATERIALIZE_MITOSHI', payload: { id: focusId, type } })}
          onClick={(id) => dispatch({ type: 'SET_FOCUS', payload: id })}
        />
        {word.is_function != null ? <CheckboxForm
          name="is_function"
          title="関数性"
          checked={word.is_function}
          edited={editedSet.has('is_function')}
          onChange={handleIsFunctionChange}
        /> : null}
        <TagForm
          name="tags"
          title="タグ"
          tags={word.tags}
          edited={editedSet.has('tags')}
          onChange={handleChange}
        />
        <LargeListForm
          name="contents"
          title="内容"
          title_h="見出し"
          title_c="内容"
          contents={word.contents}
          edited={editedSet.has('contents')}
          onChange={handleChange}
        />
        <LargeListForm
          name="variations"
          title="変化形"
          title_h="種類"
          title_c="変化形"
          contents={word.variations}
          edited={editedSet.has('variations')}
          onChange={handleChange}
        />
        <RelationForm
          name="relations"
          title="関連語"
          relations={word.relations || []}
          edited={editedSet.has('relations')}
          onChange={handleChange}
          onClick={(id) => dispatch({ type: 'SET_FOCUS', payload: id })}
        />
        {usedAsArgBy.length > 0 && (
          <div className="argUsageForm">
            <div className="formHeader">
              <p>引数としての使用 ({usedAsArgBy.length})</p>
            </div>
            <div className="argUsageList">
              {usedAsArgBy.map(w => (
                <div key={w.id} className="argUsageItem"
                  onClick={() => dispatch({ type: 'SET_FOCUS', payload: w.id })}>
                  <span className="id">{w.id}</span>
                  <span className="entry">{w.entry}</span>
                  <span className="translations">{w.translations.slice(0, 2).join(', ')}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
