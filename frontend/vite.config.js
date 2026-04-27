import fs from 'node:fs'
import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/** Defaults avoid collisions with 3000/8000/15421/18432. Override via project-root `.env`. */
const DEFAULT_BACKEND_PORT = '48721'
const DEFAULT_FRONTEND_PORT = '48722'

/** Minimal `.env` line parser (KEY=value); skips blanks and # comments. */
function parseEnvFile(content) {
  const env = {}
  for (const line of content.split(/\n/)) {
    const t = line.trim()
    if (!t || t.startsWith('#')) continue
    const eq = t.indexOf('=')
    if (eq <= 0) continue
    const key = t.slice(0, eq).trim()
    if (!key) continue
    let val = t.slice(eq + 1).trim()
    if (
      (val.startsWith('"') && val.endsWith('"')) ||
      (val.startsWith("'") && val.endsWith("'"))
    ) {
      val = val.slice(1, -1)
    }
    env[key] = val
  }
  return env
}

/**
 * Merge repo-root env files like Vite (later files override earlier).
 *
 * Do **not** use `loadEnv(mode, dir, '')` for proxy ports: with an empty prefix, Vite's
 * `loadEnv` overwrites every key from disk with `process.env`, so a stale shell
 * `BACKEND_PORT` breaks the proxy vs `run_backend.py` (which loads `.env` with override).
 */
function mergedRepoEnv(repoRoot, mode) {
  const names = [`.env`, `.env.local`, `.env.${mode}`, `.env.${mode}.local`]
  const merged = {}
  for (const name of names) {
    const p = path.join(repoRoot, name)
    if (!fs.existsSync(p)) continue
    try {
      Object.assign(merged, parseEnvFile(fs.readFileSync(p, 'utf-8')))
    } catch {
      /* ignore unreadable env files */
    }
  }
  return merged
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const repoRoot = path.resolve(__dirname, '..')
  const rootEnv = mergedRepoEnv(repoRoot, mode)
  const backendPort =
    rootEnv.BACKEND_PORT || process.env.BACKEND_PORT || DEFAULT_BACKEND_PORT
  const frontendPort =
    rootEnv.FRONTEND_PORT || process.env.FRONTEND_PORT || DEFAULT_FRONTEND_PORT
  const backendTarget = `http://127.0.0.1:${backendPort}`

  const apiAuthProxy = {
    '/api': { target: backendTarget, changeOrigin: true },
    '/auth': { target: backendTarget, changeOrigin: false },
    '/v1': { target: backendTarget, changeOrigin: true },
  }

  return {
    // Client `import.meta.env` (VITE_*): load from repo root
    envDir: repoRoot,
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: parseInt(frontendPort, 10),
      strictPort: false,
      proxy: apiAuthProxy,
    },
    preview: {
      port: parseInt(frontendPort, 10),
      strictPort: false,
      proxy: apiAuthProxy,
    },
  }
})
