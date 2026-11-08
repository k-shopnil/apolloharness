// Downloads the coarse levels of the NASA Moon Trek LRO WAC mosaic into public/tiles
// so the globe still renders with no network. Existing files are skipped.
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { dirname } from 'node:path'

const BASE =
  'https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/default/default028mm'
const MAX_LEVEL = 3
const CONCURRENCY = 8

const jobs = []
for (let z = 0; z <= MAX_LEVEL; z++) {
  for (let y = 0; y < 2 ** z; y++) {
    for (let x = 0; x < 2 ** (z + 1); x++) jobs.push({ z, y, x })
  }
}

let done = 0
let failed = 0

async function fetchTile({ z, y, x }) {
  const file = `public/tiles/${z}/${y}/${x}.jpg`
  if (!existsSync(file)) {
    const res = await fetch(`${BASE}/${z}/${y}/${x}.jpg`)
    if (!res.ok) throw new Error(`${res.status} ${z}/${y}/${x}`)
    mkdirSync(dirname(file), { recursive: true })
    writeFileSync(file, Buffer.from(await res.arrayBuffer()))
  }
}

async function worker() {
  while (jobs.length) {
    const job = jobs.pop()
    try {
      await fetchTile(job)
    } catch (err) {
      failed++
      console.error(err.message)
    }
    done++
  }
}

const total = jobs.length
await Promise.all(Array.from({ length: CONCURRENCY }, worker))
console.log(`Moon tiles: ${total - failed}/${total} ready in public/tiles`)
if (failed) {
  console.error(`${failed} tile(s) failed - rerun \`npm run fetch-tiles\` when online.`)
  // --soft: don't block dev/build when offline; the globe falls back to whatever is cached.
  if (!process.argv.includes('--soft')) process.exitCode = 1
}
