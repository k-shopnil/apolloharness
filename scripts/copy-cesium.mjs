import { cpSync, mkdirSync, rmSync } from 'node:fs'

const src = 'node_modules/cesium/Build/Cesium'
const dest = 'public/cesium'

rmSync(dest, { recursive: true, force: true })
mkdirSync(dest, { recursive: true })
for (const dir of ['Workers', 'ThirdParty', 'Assets', 'Widgets']) {
  cpSync(`${src}/${dir}`, `${dest}/${dir}`, { recursive: true })
}
