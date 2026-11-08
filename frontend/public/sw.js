// Caches NASA Moon Trek tiles as they are viewed, so previously seen detail
// still renders offline. Coarse levels ship locally in /tiles.
const CACHE = 'moon-tiles-v1'
const TILE_HOST = 'trek.nasa.gov'

self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))

async function cachedTile(request) {
  let cache
  try {
    cache = await caches.open(CACHE)
    const hit = await cache.match(request)
    if (hit) return hit
  } catch {
    // Cache unavailable: behave like a normal network request.
  }

  const res = await fetch(request)
  if (cache && res.ok) cache.put(request, res.clone()).catch(() => {})
  return res
}

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)
  if (url.hostname !== TILE_HOST || !url.pathname.includes('/tiles/Moon/')) return
  event.respondWith(cachedTile(event.request))
})
