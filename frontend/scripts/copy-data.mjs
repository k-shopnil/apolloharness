// Copies the engine's static data into public/data so the app can fetch it
// offline: data/missions.json and data/precomputed/tracks/*.json.
import { cpSync, existsSync, mkdirSync, rmSync } from 'node:fs'

const root = '../data'
const dest = 'public/data'

if (!existsSync(`${root}/missions.json`)) {
  console.warn('[copy-data] ../data not found - skipping (run from the monorepo)')
  process.exit(0)
}

rmSync(dest, { recursive: true, force: true })
mkdirSync(`${dest}/precomputed`, { recursive: true })
cpSync(`${root}/missions.json`, `${dest}/missions.json`)
cpSync(`${root}/precomputed/tracks`, `${dest}/precomputed/tracks`, { recursive: true })
console.log('[copy-data] copied missions.json + precomputed tracks to public/data')
