import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './components/App/App.jsx'
import { DictionaryProvider } from './store/DictionaryContext.jsx'
import { PageProvider } from './store/PageContext';
import './styles/index.scss'

createRoot(document.getElementById('root')).render(
  <DictionaryProvider>
    <PageProvider>
      <App />
    </PageProvider>
  </DictionaryProvider>
);