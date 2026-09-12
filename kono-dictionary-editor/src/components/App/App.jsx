// src/components/App.jsx
import { useCallback, useEffect, useRef } from 'react';
import './App.scss';
import '../../styles/index.scss';

import { WordTree } from '../TreeView/TreeView';
import DetailsFrame from '../DetailFrame/DetailFrame';
import { SearchFrame, EmptyFrame } from '../OtherFrames/OtherFrames';
import { MenuBar } from '../CommonForms';
import { useDictState, useDictDispatch } from '../../store/DictionaryContext';
import { BUNDLED_FINGERPRINT } from '../../store/bundledDictionary.js';
import { usePageState, usePageDispatch } from '../../store/PageContext';

function PageTab({ tabs, activeTab, setActiveTab }) {
  return (
    <div className="menuBar pageTab">
      {tabs.map((tab, i) => (
        <button key={i} onClick={() => setActiveTab(tab)} className={`tab ${tab === activeTab ? "active" : ""}`}>
          {tab}
        </button>
      ))}
    </div>
  );
}

export default function App() {
  const { words } = useDictState();
  const dictDispatch = useDictDispatch();
  const dictionaryFileHandle = useRef(null);
  const { leftWidth, pageTabs } = usePageState();
  const pageDispatch = usePageDispatch();

  const pages = [
    { title: '単語', component: <WordTree /> },
    { title: '詳細', component: <DetailsFrame /> },
    { title: '検索', component: <SearchFrame /> }
  ];

  const leftComponent = pages.find(p => p.title === pageTabs.left.active)?.component || <EmptyFrame />;
  const rightComponent = pages.find(p => p.title === pageTabs.right.active)?.component || <EmptyFrame />;

  const setActiveTab = (side) => (tab) => {
    pageDispatch({ type: 'SET_TAB', payload: { side, tab } });
  };

  const openSearchTab = useCallback(() => {
    const side = pageTabs.left.display.includes('検索') ? 'left' : 'right';
    pageDispatch({ type: 'OPEN_TAB', payload: { side, tab: '検索' } });
  }, [pageTabs.left.display, pageDispatch]);

  // 分割バーの操作
  const handleMouseMove = useCallback((e) => {
    const newWidth = (e.clientX / window.innerWidth) * 100;
    pageDispatch({ type: 'SET_LEFT_WIDTH', payload: newWidth });
  }, [pageDispatch]);

  const handleMouseUp = useCallback(() => {
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
    document.body.style.userSelect = '';
  }, [handleMouseMove]);

  const handleMouseDown = useCallback(() => {
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.userSelect = 'none';
  }, [handleMouseMove, handleMouseUp]);

  // メニューアクション（必要に応じて増やせる）
  const handleDownload = useCallback(() => {
    const blob = new Blob([JSON.stringify({ words }, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'dictionary.json';
    a.click();
  }, [words]);

  const loadDictionaryFile = useCallback((file) => {
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const data = JSON.parse(ev.target.result);
        if (data.words) {
          dictDispatch({ type: 'SET_DICTIONARY', payload: { words: data.words } });
        }
      } catch {
        alert('JSONの読み込みに失敗しました');
      }
    };
    reader.readAsText(file);
  }, [dictDispatch]);

  const handleUpload = useCallback(async () => {
    // File System Access API が使える環境では、読み込んだファイルへの
    // 書き込み権限も保持して「ファイルを上書き」で再利用する。
    if ('showOpenFilePicker' in window) {
      try {
        const [handle] = await window.showOpenFilePicker({
          types: [{
            description: 'JSON辞書',
            accept: { 'application/json': ['.json'] },
          }],
          multiple: false,
        });
        dictionaryFileHandle.current = handle;
        loadDictionaryFile(await handle.getFile());
      } catch (error) {
        if (error.name !== 'AbortError') {
          alert(`JSONの読み込みに失敗しました: ${error.message}`);
        }
      }
      return;
    }

    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'application/json';
    input.onchange = (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      loadDictionaryFile(file);
    };
    input.click();
  }, [loadDictionaryFile]);

  const handleSave = useCallback(() => {
    localStorage.setItem('dictionary', JSON.stringify({ words, base: BUNDLED_FINGERPRINT }));
    dictDispatch({ type: 'CLEAR_EDITED' });
  }, [dictDispatch, words]);

  const handleOverwriteFile = useCallback(async () => {
    if (import.meta.env.DEV) {
      try {
        // ソースJSONの更新でViteがページを再読み込みしても、古いlocalStorageが
        // 新しい組み込み辞書を隠さないよう、書き込み前に消しておく。
        localStorage.removeItem('dictionary');
        const response = await fetch(`${import.meta.env.BASE_URL}__write_dictionary`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ words }),
        });
        const result = await response.json();
        if (!response.ok || !result.ok) {
          throw new Error(result.error || `HTTP ${response.status}`);
        }
        dictDispatch({ type: 'CLEAR_EDITED' });
      } catch (error) {
        alert(`src/data/konomeno-v5.json の上書きに失敗しました: ${error.message}`);
      }
      return;
    }

    if (!('showSaveFilePicker' in window)) {
      alert('このブラウザはファイルの直接上書きに対応していません。ChromeまたはEdgeで開いてください。');
      return;
    }

    try {
      let handle = dictionaryFileHandle.current;
      if (!handle) {
        handle = await window.showSaveFilePicker({
          suggestedName: 'konomeno-v5.json',
          types: [{
            description: 'JSON辞書',
            accept: { 'application/json': ['.json'] },
          }],
        });
      }

      const writable = await handle.createWritable();
      await writable.write(`${JSON.stringify({ words }, null, 2)}\n`);
      await writable.close();
      dictionaryFileHandle.current = handle;
      dictDispatch({ type: 'CLEAR_EDITED' });
    } catch (error) {
      if (error.name !== 'AbortError') {
        alert(`ファイルの上書きに失敗しました: ${error.message}`);
      }
    }
  }, [dictDispatch, words]);

  const menuItems = [
    { title: '読み込み', onClick: handleUpload },
    { title: 'ブラウザに保存', onClick: handleSave, shortcut: 'Ctrl/⌘+S' },
    { title: import.meta.env.DEV ? '辞書本体を上書き' : 'ファイルを上書き', onClick: handleOverwriteFile, shortcut: 'Ctrl/⌘+Shift+S' },
    { title: 'ダウンロード', onClick: handleDownload },
  ];

  // ショートカットキー登録
  useEffect(() => {
    const handleShortcut = (e) => {
      const key = e.key.toLowerCase();
      if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        e.preventDefault();
        openSearchTab();
      }
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && key === 's') {
        e.preventDefault();
        handleOverwriteFile();
      } else if ((e.ctrlKey || e.metaKey) && key === 's') {
        e.preventDefault();
        handleSave();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'o') {
        e.preventDefault();
        handleUpload();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
        e.preventDefault();
        handleDownload();
      }
    };
    window.addEventListener('keydown', handleShortcut);
    return () => window.removeEventListener('keydown', handleShortcut);
  }, [handleDownload, handleOverwriteFile, handleSave, handleUpload, openSearchTab]);

  return (
    <div className="window">
      <MenuBar items={menuItems} />
      <div className="mainWindow">
        <div className="leftContainer" style={{ width: `${leftWidth}%` }}>
          <PageTab
            tabs={pageTabs.left.display}
            activeTab={pageTabs.left.active}
            setActiveTab={setActiveTab('left')}
          />
          <div className="innerLeftContainer">{leftComponent}</div>
        </div>
        <div className="divider" onMouseDown={handleMouseDown}></div>
        <div className="rightContainer" style={{ width: `${100 - leftWidth}%` }}>
          <PageTab
            tabs={pageTabs.right.display}
            activeTab={pageTabs.right.active}
            setActiveTab={setActiveTab('right')}
          />
          <div className="innerRightContainer">{rightComponent}</div>
        </div>
      </div>
    </div>
  );
}
