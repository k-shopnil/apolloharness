import { useState } from 'react'
import craterSurface from '../assets/crater-surface.jpg'
import { MissionDetails } from './MissionDetails'
import { formatCoords, type LocatedMission } from '../data/missions'
import { horizonLabel, useTrack } from '../data/tracks'
import './SiteView.css'

interface SiteViewProps {
  mission: LocatedMission
  onBack: () => void
  onCompare: () => void
  onOpenProvenance: () => void
}

const layers = ['Topography'] as const
type Layer = (typeof layers)[number]

export function SiteView({ mission, onBack, onCompare, onOpenProvenance }: SiteViewProps) {
  const lookup = useTrack(mission.id)
  const data = lookup.state === 'ready' ? lookup.data : null
  const [enabled, setEnabled] = useState<Set<Layer>>(new Set(['Topography']))
  const toggle = (layer: Layer) =>
    setEnabled((prev) => {
      const next = new Set(prev)
      if (next.has(layer)) next.delete(layer)
      else next.add(layer)
      return next
    })

  return (
    <>
      <section className="site-map">
        <div
          className={`site-map__terrain${enabled.has('Topography') ? '' : ' site-map__terrain--flat'}`}
          style={{ backgroundImage: `url(${craterSurface})` }}
        />
        <div className="site-map__shade" />

        <svg
          className="site-map__overlay"
          viewBox="0 0 919 976"
          preserveAspectRatio="xMidYMid slice"
          aria-hidden
        >
          <line x1="423" y1="0" x2="423" y2="976" stroke="rgba(255,255,255,0.25)" />
          <line x1="0" y1="404" x2="919" y2="404" stroke="rgba(255,255,255,0.25)" />
          <g stroke="#ff4d00" strokeWidth="2" fill="none">
            <circle cx="423" cy="404" r="5" />
            <line x1="403" y1="404" x2="415" y2="404" />
            <line x1="431" y1="404" x2="443" y2="404" />
            <line x1="423" y1="384" x2="423" y2="396" />
            <line x1="423" y1="412" x2="423" y2="424" />
          </g>
        </svg>

        <p className="site-map__tag site-map__tag--psr">ILLUSTRATIVE TERRAIN IMAGE · NOT THIS SITE</p>

        <button type="button" className="site-map__back" onClick={onBack}>
          ◀ BACK TO GLOBAL FLEET
        </button>

        <div className="site-map__dock">
          <div className="site-map__hud">
            <p>
              {formatCoords(mission.lat, mission.lon)} &nbsp;|&nbsp; ELEVATION:{' '}
              {data?.terrain.elevation_m == null ? 'UNAVAILABLE' : `${Math.round(data.terrain.elevation_m).toLocaleString('en-US')}m`}
            </p>
            <p className="site-map__hud-dim">
              {data?.terrain.dem_product ?? 'TERRAIN UNAVAILABLE'} &nbsp;|&nbsp;{' '}
              {data ? horizonLabel(data.track.horizon_model).toUpperCase() : 'NO TRACK'}
            </p>
          </div>
          <div className="site-map__chips">
            {layers.map((layer) => (
              <button
                key={layer}
                type="button"
                className={`chip${enabled.has(layer) ? ' chip--on' : ''}`}
                aria-pressed={enabled.has(layer)}
                onClick={() => toggle(layer)}
              >
                {enabled.has(layer) ? '☑' : '☐'} {layer}
              </button>
            ))}
            <button type="button" className="chip chip--accent" onClick={onOpenProvenance}>
              DATA PROVENANCE ↗
            </button>
          </div>
        </div>
      </section>

      <aside className="site-panel">
        <div className="site-panel__scroll">
          <MissionDetails mission={mission} onCompare={onCompare} onOpenProvenance={onOpenProvenance} />
        </div>
      </aside>
    </>
  )
}
