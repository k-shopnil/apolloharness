import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Fonts are bundled, not loaded from Google, so the app looks the same with the network off.
// One typeface throughout: Inter, the face of the lobby countdown.
import '@fontsource/inter/latin-400.css'
import '@fontsource/inter/latin-500.css'
import '@fontsource/inter/latin-600.css'
import '@fontsource/inter/latin-700.css'
import '@fontsource/inter/latin-800.css'
import './index.css'
import { Root } from './Root.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      // Offline tile caching is an enhancement; the globe works without it.
    })
  })
}
