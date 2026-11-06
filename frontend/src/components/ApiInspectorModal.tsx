import { useEffect, useState } from 'react'
import { API_BASE_URL, testAllEndpoints, type EndpointTestResult } from '../services/api'
import './ApiInspectorModal.css'

interface ApiInspectorModalProps {
  onClose: () => void
}

export function ApiInspectorModal({ onClose }: ApiInspectorModalProps) {
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<EndpointTestResult[]>([])
  const [selectedIdx, setSelectedIdx] = useState<number>(0)

  const runTests = async () => {
    setLoading(true)
    try {
      const data = await testAllEndpoints()
      setResults(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    runTests()
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const selectedResult = results[selectedIdx]
  const passCount = results.filter((r) => r.status === 'PASS').length

  return (
    <div className="api-modal" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="api-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="api-title">
        <header className="api-modal__header">
          <div>
            <p className="api-modal__eyebrow">FASTAPI COMPUTE BACKEND DIAGNOSTICS</p>
            <h2 id="api-title">{'// MISSION CONTROL API EXPLORER'}</h2>
          </div>
          <div className="api-modal__actions">
            <button
              type="button"
              className="api-modal__btn-run"
              onClick={runTests}
              disabled={loading}
            >
              {loading ? 'TESTING ENDPOINTS…' : '▶ RUN ALL API TESTS'}
            </button>
            <button type="button" className="api-modal__close" onClick={onClose}>
              [ ✕ CLOSE ]
            </button>
          </div>
        </header>

        <div className="api-modal__summary">
          <div className="api-stat">
            <span>TARGET HOST</span>
            <strong>{API_BASE_URL}</strong>
          </div>
          <div className="api-stat">
            <span>STATUS</span>
            <strong className={passCount === results.length && results.length > 0 ? 'text-ok' : 'text-amber'}>
              {results.length === 0
                ? 'TESTING…'
                : passCount > 0
                  ? `${passCount}/${results.length} ENDPOINTS PASSING`
                  : 'BACKEND OFFLINE · SERVING PDS FIXTURES'}
            </strong>
          </div>
          <div className="api-stat">
            <span>RUNTIME MODE</span>
            <strong className={passCount > 0 ? 'text-ok' : 'text-amber'}>
              {passCount > 0
                ? 'DETERMINISTIC LIVE COMPUTE (SPICE + LOLA + PDS)'
                : 'OFFLINE STANDALONE PWA (NASA ARCHIVAL FIXTURES)'}
            </strong>
          </div>
        </div>

        <div className="api-modal__body">
          <aside className="api-modal__sidebar">
            <p className="api-modal__nav-label">ENDPOINTS (5 / 5)</p>
            <nav className="api-modal__nav">
              {results.map((r, i) => (
                <button
                  key={r.endpoint}
                  type="button"
                  className={`api-nav-item${selectedIdx === i ? ' api-nav-item--active' : ''}`}
                  onClick={() => setSelectedIdx(i)}
                >
                  <span className={`api-badge api-badge--${r.status.toLowerCase()}`}>
                    {r.status === 'PASS' ? '200' : r.status === 'FAIL' ? 'ERR' : '…'}
                  </span>
                  <div className="api-nav-info">
                    <strong className="api-nav-name">{r.endpoint}</strong>
                    <span className="api-nav-url">{r.url}</span>
                  </div>
                  {r.latencyMs !== undefined && (
                    <span className="api-nav-latency">{r.latencyMs}ms</span>
                  )}
                </button>
              ))}
            </nav>
          </aside>

          <main className="api-modal__content">
            {selectedResult ? (
              <div className="api-viewer">
                <div className="api-viewer__bar">
                  <div className="api-viewer__meta">
                    <span className="api-method">GET</span>
                    <code className="api-url">{API_BASE_URL}{selectedResult.url}</code>
                  </div>
                  <div className="api-viewer__status">
                    <span className={`status-pill status-pill--${selectedResult.status.toLowerCase()}`}>
                      {selectedResult.status} {selectedResult.statusCode ? `(${selectedResult.statusCode})` : ''}
                    </span>
                    {selectedResult.latencyMs !== undefined && (
                      <span className="latency-pill">{selectedResult.latencyMs} ms</span>
                    )}
                  </div>
                </div>

                <div className="api-viewer__payload">
                  <pre className="json-box">
                    {selectedResult.error
                      ? `// Request Failed:\n${selectedResult.error}`
                      : JSON.stringify(selectedResult.data, null, 2)}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="api-viewer__empty">Running endpoint verification…</div>
            )}
          </main>
        </div>

        <footer className="api-modal__footer">
          <span>SPECIFICATION: APOLLOHARNESS PLATE 01/02/03</span>
          <span className="api-modal__foot-right">
            OFFLINE FALLBACK: READY · CORS: CONFIGURED
          </span>
        </footer>
      </div>
    </div>
  )
}

