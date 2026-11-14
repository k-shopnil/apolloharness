import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import { Gateway } from './gateway/Gateway'

// "/" is the gateway (countdown lobby); "/app" is the mission interface.
// Firebase rewrites every path to index.html, so /app deep-links and reloads work.
const APP_PATH = '/app'
const GATEWAY_TITLE = 'ApolloHarness by Team Chhayanautical | NASA Space Apps Challenge 2026'
const APP_TITLE = 'HarnessApollo · Lunar Mission Interface'

// Once the prefetch has resolved, render the module directly: going through
// lazy() again would still suspend for a tick and flash the fallback.
let appModule: typeof import('./App') | null = null
const loadApp = () =>
  import('./App').then((m) => {
    appModule = m
    return m
  })
const LazyApp = lazy(loadApp)

type View = 'gateway' | 'app'

const viewFromLocation = (): View => (window.location.pathname.replace(/\/+$/, '') === APP_PATH ? 'app' : 'gateway')

export function Root() {
  const [view, setView] = useState<View>(viewFromLocation)

  useEffect(() => {
    const sync = () => setView(viewFromLocation())
    window.addEventListener('popstate', sync)
    return () => window.removeEventListener('popstate', sync)
  }, [])

  useEffect(() => {
    document.title = view === 'app' ? APP_TITLE : GATEWAY_TITLE
  }, [view])

  // While the lobby is up, fetch the interface (and the Cesium globe chunk) in
  // the background so takeoff lands straight in a ready app.
  useEffect(() => {
    if (view !== 'gateway') return
    const prefetch = () => {
      void loadApp().catch(() => {})
      void import('./components/MoonGlobe').catch(() => {})
    }
    if ('requestIdleCallback' in window) {
      const id = window.requestIdleCallback(prefetch, { timeout: 2500 })
      return () => window.cancelIdleCallback(id)
    }
    const id = setTimeout(prefetch, 1200)
    return () => clearTimeout(id)
  }, [view])

  const enter = useCallback(() => {
    window.history.pushState(null, '', APP_PATH)
    setView('app')
  }, [])

  if (view === 'gateway') return <Gateway onEnter={enter} />

  const App = appModule?.default ?? LazyApp
  return (
    <Suspense
      fallback={
        <div className="app">
          <div className="globe globe--loading">Preparing mission interface…</div>
        </div>
      }
    >
      <div className="app-enter">
        <App />
      </div>
    </Suspense>
  )
}
