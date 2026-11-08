import { useEffect } from 'react'
import type { Mission } from '../data/missions'
import { horizonLabel, useTrack, type Track } from '../data/tracks'
import './ProvenanceModal.css'

interface ProvenanceModalProps {
  mission: Mission
  onClose: () => void
}

const W = 600
const H = 160

/** Polyline for one column; null samples break the line. Y range is -10..+90 degrees. */
function linePath(values: (number | null)[], hours: number[]): string {
  const maxH = hours[hours.length - 1] || 1
  let d = ''
  let pen = false
  values.forEach((v, i) => {
    if (v === null) {
      pen = false
      return
    }
    const x = (hours[i] / maxH) * W
    const y = H - ((Math.max(-10, Math.min(90, v)) + 10) / 100) * H
    d += `${pen ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`
    pen = true
  })
  return d
}

function ElevationChart({ track }: { track: Track }) {
  const c = track.columns
  const zeroY = H - (10 / 100) * H
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Sun and Earth elevation over the 29.5-day window" preserveAspectRatio="none" width="100%" height="100%">
      <line x1="0" x2={W} y1={zeroY} y2={zeroY} stroke="rgba(255,255,255,0.35)" strokeDasharray="4 4" />
      <path d={linePath(c.earth_elevation_deg, c.hours_from_start)} fill="none" stroke="#00cfff" strokeWidth="1.5" />
      <path d={linePath(c.sun_elevation_deg, c.hours_from_start)} fill="none" stroke="#d4a017" strokeWidth="1.5" />
    </svg>
  )
}

export function ProvenanceModal({ mission, onClose }: ProvenanceModalProps) {
  const lookup = useTrack(mission.id)
  const data = lookup.state === 'ready' ? lookup.data : null

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="modal" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal__dialog" role="dialog" aria-modal="true" aria-labelledby="pds-title">
        <header className="modal__header">
          <div>
            <p className="modal__eyebrow">EVIDENCE &amp; DATA PROVENANCE</p>
            <h2 id="pds-title">{`// ${mission.name.toUpperCase()}`}</h2>
          </div>
          <button type="button" className="modal__close" onClick={onClose}>
            [ ✕ CLOSE ]
          </button>
        </header>

        <div className="modal__body">
          <section className="panel">
            <h3>A // SUN &amp; EARTH ELEVATION (29.5-DAY WINDOW)</h3>
            <p>
              {data
                ? `Computed from SPICE ephemeris at ${mission.targetSite}. Cyan = Earth, amber = Sun; dashed line is 0° (horizon).`
                : lookup.state === 'loading'
                  ? 'Loading…'
                  : `Unavailable · ${lookup.state === 'none' || lookup.state === 'error' ? lookup.reason : ''}`}
            </p>
            {data && (
              <div className="chart chart--short">
                <ElevationChart track={data.track} />
                <span className="chart__label chart__label--bl">0° HORIZON</span>
                <span className="chart__label chart__label--br">+29.5 DAYS</span>
              </div>
            )}
          </section>

          <section className="ids">
            <div className="ids__head">
              <h3>B // DATA SOURCES</h3>
              <span>{data ? horizonLabel(data.track.horizon_model).toUpperCase() : 'NO TRACK'}</span>
            </div>
            {data?.terrain.dem_product && (
              <div className="ids__row">
                <strong>TERRAIN</strong>
                <span>{data.terrain.dem_product}</span>
              </div>
            )}
            {data?.terrain.source_dataset && (
              <div className="ids__row">
                <strong>DEM FILE</strong>
                <span>{data.terrain.source_dataset}</span>
              </div>
            )}
            <div className="ids__row">
              <strong>COORDINATE</strong>
              <span>{mission.coordinateProvenance}</span>
            </div>
            {mission.sources.map((s) => (
              <div className="ids__row" key={s.url}>
                <strong>{s.publisher.toUpperCase()}</strong>
                <span>
                  <a href={s.url} target="_blank" rel="noreferrer">
                    {s.title}
                  </a>
                </span>
              </div>
            ))}
          </section>

          <p className="details__note">
            Derived output computed by the HarnessApollo engine. Human scientific review is pending; this is not an
            official NASA product.
          </p>
        </div>
      </div>
    </div>
  )
}
