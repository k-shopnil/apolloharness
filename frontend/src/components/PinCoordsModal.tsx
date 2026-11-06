import React, { useState, useEffect } from 'react'
import './PinCoordsModal.css'

interface PinCoordsModalProps {
  onClose: () => void
  onSubmit: (lat: number, lon: number, label?: string) => void
  initialLat?: number
  initialLon?: number
}

interface Preset {
  name: string
  lat: number
  lon: number
  category: 'artemis' | 'clps' | 'anchor'
}

const PRESETS: Preset[] = [
  { name: 'Shackleton Crater Rim', lat: -89.9, lon: 0.0, category: 'artemis' },
  { name: 'Connecting Ridge', lat: -89.44, lon: -137.4, category: 'artemis' },
  { name: 'Malapert Mountain', lat: -84.9, lon: 12.9, category: 'artemis' },
  { name: 'Mons Mouton (VIPER)', lat: -84.8, lon: -31.6, category: 'clps' },
  { name: 'Haworth Crater Ridge', lat: -87.4, lon: -5.1, category: 'artemis' },
  { name: 'Apollo 11 Tranquillity Base', lat: 0.674, lon: 23.473, category: 'anchor' },
  { name: 'Apollo 17 Taurus-Littrow', lat: 20.191, lon: 30.772, category: 'anchor' },
  { name: 'Chandrayaan-3 Shiv Shakti', lat: -69.374, lon: 32.32, category: 'anchor' },
]

export function PinCoordsModal({ onClose, onSubmit, initialLat, initialLon }: PinCoordsModalProps) {
  const [latStr, setLatStr] = useState<string>(initialLat !== undefined ? initialLat.toFixed(4) : '-84.8000')
  const [lonStr, setLonStr] = useState<string>(initialLon !== undefined ? initialLon.toFixed(4) : '29.2000')
  const [label, setLabel] = useState<string>('Custom Candidate Site')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const handleApplyPreset = (p: Preset) => {
    setLatStr(p.lat.toString())
    setLonStr(p.lon.toString())
    setLabel(p.name)
    setError(null)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const lat = parseFloat(latStr)
    const lon = parseFloat(lonStr)

    if (isNaN(lat) || lat < -90 || lat > 90) {
      setError('Latitude must be a valid number between -90.0° and +90.0°')
      return
    }
    if (isNaN(lon) || lon < -180 || lon > 180) {
      setError('Longitude must be a valid number between -180.0° and +180.0°')
      return
    }

    setError(null)
    onSubmit(lat, lon, label.trim() || undefined)
    onClose()
  }

  return (
    <div className="pin-modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="pin-modal-title">
      <div className="pin-modal" onClick={(e) => e.stopPropagation()}>
        <header className="pin-modal__head">
          <div className="pin-modal__title-group">
            <span className="pin-modal__dot" />
            <h2 id="pin-modal-title">EVALUATE CUSTOM COORDINATES</h2>
          </div>
          <button type="button" className="pin-modal__close" onClick={onClose} aria-label="Close dialog">
            ✕
          </button>
        </header>

        <p className="pin-modal__desc">
          Drop a landing target anywhere on the Moon. Antigravity calculates horizon masks from LOLA DEM altimetry,
          SPICE ephemeris Sun/Earth countdowns, and PSR cold-trap proximity with zero mock interpolation.
        </p>

        <form onSubmit={handleSubmit} className="pin-modal__form">
          <div className="pin-modal__inputs">
            <div className="pin-modal__field">
              <label htmlFor="pin-lat">LATITUDE (DEG: -90.0° TO +90.0°)</label>
              <input
                id="pin-lat"
                type="number"
                step="any"
                min="-90"
                max="90"
                value={latStr}
                onChange={(e) => setLatStr(e.target.value)}
                required
                autoFocus
                placeholder="-84.80"
              />
            </div>
            <div className="pin-modal__field">
              <label htmlFor="pin-lon">LONGITUDE (DEG: -180.0° TO +180.0°)</label>
              <input
                id="pin-lon"
                type="number"
                step="any"
                min="-180"
                max="180"
                value={lonStr}
                onChange={(e) => setLonStr(e.target.value)}
                required
                placeholder="29.20"
              />
            </div>
          </div>

          <div className="pin-modal__field">
            <label htmlFor="pin-label">SITE IDENTIFIER / MISSION LABEL</label>
            <input
              id="pin-label"
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. Artemis III Secondary Candidate"
            />
          </div>

          {error && <div className="pin-modal__error">⚠️ {error}</div>}

          <div className="pin-modal__presets">
            <div className="pin-modal__presets-title">POPULAR LUNAR REFERENCE TARGETS:</div>
            <div className="pin-modal__presets-list">
              {PRESETS.map((p) => (
                <button
                  key={p.name}
                  type="button"
                  className="pin-modal__preset-pill"
                  onClick={() => handleApplyPreset(p)}
                >
                  {p.name} ({p.lat > 0 ? `+${p.lat}` : p.lat}°, {p.lon > 0 ? `+${p.lon}` : p.lon}°)
                </button>
              ))}
            </div>
          </div>

          <footer className="pin-modal__actions">
            <button type="button" className="pin-modal__btn-cancel" onClick={onClose}>
              CANCEL
            </button>
            <button type="submit" className="pin-modal__btn-submit">
              EVALUATE &amp; DROP PIN ➔
            </button>
          </footer>
        </form>
      </div>
    </div>
  )
}
