import { useEffect, useRef, useState } from 'react'
import { nowUtc, type CustomRequest } from '../data/api'
import { Icon } from './Icon'
import './PointForm.css'

interface Props {
  onSubmit: (request: CustomRequest) => void
  onClose: () => void
}

/** Typed coordinates for the live engine. Longitude accepts -180..180 or 0..360 (east positive). */
export function PointForm({ onSubmit, onClose }: Props) {
  const [lat, setLat] = useState('')
  const [lon, setLon] = useState('')
  const [utc, setUtc] = useState(nowUtc().slice(0, 16))
  const [error, setError] = useState<string | null>(null)
  const first = useRef<HTMLInputElement>(null)

  useEffect(() => {
    first.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const la = Number(lat)
    let lo = Number(lon)
    if (lat.trim() === '' || !Number.isFinite(la) || la < -90 || la > 90) return setError('Latitude must be between -90 and 90 (south is negative).')
    if (lon.trim() === '' || !Number.isFinite(lo) || lo < -180 || lo > 360) return setError('Longitude must be between -180 and 180, or 0 and 360 east.')
    if (lo > 180) lo -= 360
    if (!utc) return setError('Choose a start time.')
    onSubmit({ lat: la, lon: lo, utc: `${utc}:00Z` })
  }

  return (
    <div className="point-form__backdrop" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="point-form" role="dialog" aria-modal="true" aria-labelledby="point-form-title" onSubmit={submit} noValidate>
        <div className="point-form__head">
          <h2 id="point-form-title">Analyse a point</h2>
          <button type="button" className="point-form__x" onClick={onClose} aria-label="Close">
            <Icon name="close" size={16} />
          </button>
        </div>
        <p className="point-form__lead">
          Sunlight, Earth contact and terrain for any spot on the Moon, computed live. You can also click anywhere on the
          globe.
        </p>
        <div className="point-form__row">
          <label>
            <span>Latitude (°)</span>
            <input ref={first} inputMode="decimal" placeholder="-84.79" value={lat} onChange={(e) => setLat(e.target.value)} />
          </label>
          <label>
            <span>Longitude (° east)</span>
            <input inputMode="decimal" placeholder="29.20" value={lon} onChange={(e) => setLon(e.target.value)} />
          </label>
        </div>
        <label>
          <span>Start time (UTC)</span>
          <input type="datetime-local" value={utc} onChange={(e) => setUtc(e.target.value)} />
        </label>
        {error && (
          <p className="point-form__error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="point-form__go">
          Analyse
        </button>
      </form>
    </div>
  )
}
