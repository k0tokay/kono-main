import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { rename, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const dictionaryPath = resolve(process.cwd(), 'src/data/konomeno-v5.json')
const dictionaryTempPath = `${dictionaryPath}.tmp`

function dictionaryWriter() {
  return {
    name: 'kono-dictionary-writer',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        const pathname = new URL(req.url, 'http://localhost').pathname
        if (req.method !== 'POST' || !pathname.endsWith('/__write_dictionary')) {
          next()
          return
        }

        try {
          const chunks = []
          let size = 0
          for await (const chunk of req) {
            size += chunk.length
            if (size > 50 * 1024 * 1024) {
              throw new Error('辞書データが大きすぎます')
            }
            chunks.push(chunk)
          }

          const dictionary = JSON.parse(Buffer.concat(chunks).toString('utf8'))
          if (!dictionary || !Array.isArray(dictionary.words)) {
            throw new Error('words配列を持つ辞書JSONではありません')
          }

          // この保存をViteの外部変更として扱うとページ全体が再読み込みされ、
          // 開いているツリーの状態が失われる。書き込み中だけ監視対象から外す。
          await server.watcher.unwatch(dictionaryPath)
          try {
            await writeFile(dictionaryTempPath, `${JSON.stringify(dictionary, null, 2)}\n`, 'utf8')
            await rename(dictionaryTempPath, dictionaryPath)
          } finally {
            server.watcher.add(dictionaryPath)
          }
          res.statusCode = 200
          res.setHeader('Content-Type', 'application/json; charset=utf-8')
          res.end(JSON.stringify({ ok: true }))
        } catch (error) {
          res.statusCode = 400
          res.setHeader('Content-Type', 'application/json; charset=utf-8')
          res.end(JSON.stringify({ ok: false, error: error.message }))
        }
      })
    },
  }
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), dictionaryWriter()],
  // GitHub Pages のパス．モノレポからのデプロイでは VITE_BASE=/<リポジトリ名>/ を渡す．
  base: process.env.VITE_BASE ?? "/kono-dictionary-editor/",
  css: {
    preprocessorOptions: {
      scss: {
        api: "modern-compiler",
      },
    }
  }
})
