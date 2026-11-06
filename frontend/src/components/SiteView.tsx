import { useEffect, useState } from 'react'
import craterSurface from '../assets/crater-surface.jpg'
import { MissionDetails } from './MissionDetails'
import { formatCoords, type Mission } from '../data/missions'
import { computeLocalSiteGeometry, fetchSiteGeometry, type SiteGeometry } from '../services/siteGeometry'
import './SiteView.css'

interface SiteViewProps {
  mission: Mission
  onBack: () => void
  onCompare: () => void
  onOpenProvenance: () => void
}

const layers = ['Topography', 'Slope Heatmap', 'PSR Mask'] as const
type Layer = (typeof layers)[number]

export function SiteView({ mission, onBack, onCompare, onOpenProvenance }: SiteViewProps) {
  const [enabled, setEnabled] = useState<Set<Layer>>(new Set(['Topography']))
  const [geometry, setGeometry] = useState<SiteGeometry>(() =>
    computeLocalSiteGeometry(mission.lat, mission.lon)
  )

  useEffect(() => {
    let active = true
    fetchSiteGeometry(mission.lat, mission.lon).then((data) => {
      if (active) setGeometry(data)
    })
    return () => {
      active = false
    }
  }, [mission.lat, mission.lon])

  const toggle = (layer: Layer) =>
    setEnabled((prev) => {
      const next = new Set(prev)
      if (next.has(layer)) next.delete(layer)
      else next.add(layer)
      return next
    })

  const sunAzimuthStr = geometry.sun.azimuth_deg.toFixed(0).padStart(3, '0')
  const sunElevSign = geometry.sun.elevation_deg >= 0 ? '+' : ''
  const earthElevSign = geometry.earth.elevation_deg >= 0 ? '+' : ''

  return (
    <>
      <section className="site-map">
        <div
          className={`site-map__terrain${enabled.has('Topography') ? '' : ' site-map__terrain--flat'}`}
          style={{ backgroundImage: `url(${craterSurface})` }}
        />
        {enabled.has('Slope Heatmap') && <div className="site-map__slope" />}
        {enabled.has('PSR Mask') && <div className="site-map__psr" />}
        <div className="site-map__shade" />

        <svg
          className="site-map__overlay"
          viewBox="0 0 919 976"
          preserveAspectRatio="xMidYMid slice"
          aria-hidden
        >
          <line x1="423" y1="0" x2="423" y2="976" stroke="rgba(255,255,255,0.25)" />
          <line x1="0" y1="404" x2="919" y2="404" stroke="rgba(255,255,255,0.25)" />
          <ellipse cx="423" cy="404" rx="140" ry="81" fill="none" stroke="#fff" strokeWidth="1.5" strokeDasharray="7 5" />
          <text x="529" y="385" fill="rgba(255,255,255,0.5)" fontSize="13.9" fontFamily="JetBrains Mono" letterSpacing="0.84">
            {mission.ellipseKm[0] * 2}km × {mission.ellipseKm[1] * 2}km LANDING ELLIPSE
          </text>
          <line x1="427" y1="392" x2="480" y2="290" stroke="#4ade80" strokeWidth="1.5" strokeDasharray="3 4" />
          <line x1="430" y1="410" x2="521" y2="484" stroke="#00cfff" strokeWidth="1.5" strokeDasharray="3 4" />
          <circle cx="521" cy="484" r="5.5" fill="#00cfff" />
          <line x1="5" y1="132" x2="72" y2="85" stroke="#d4a017" strokeWidth="2" />
          <g stroke="#ff4d00" strokeWidth="2" fill="none">
            <circle cx="423" cy="404" r="5" />
            <line x1="403" y1="404" x2="415" y2="404" />
            <line x1="431" y1="404" x2="443" y2="404" />
            <line x1="423" y1="384" x2="423" y2="396" />
            <line x1="423" y1="412" x2="423" y2="424" />
          </g>
        </svg>

        <div className="site-map__tag site-map__tag--sun">
          <p className="site-map__tag-main" style={{ color: 'var(--amber)' }}>
            ☀ Sun Azimuth: {sunAzimuthStr}° | Elev: {sunElevSign}{geometry.sun.elevation_deg.toFixed(1)}°
          </p>
          <p className="site-map__tag-sub">
            {geometry.sun.terrain_clearance_summary || `Elevation: ${geometry.sun.elevation_deg.toFixed(1)}° above horizon`}
          </p>
        </div>
        <p className="site-map__tag site-map__tag--earth">
          📡 Earth LOS: {earthElevSign}{geometry.earth.elevation_deg.toFixed(1)}° ({geometry.earth.rtt_str || 'RTT: ~2.56s'})
        </p>
        <p className="site-map__tag site-map__tag--psr">
          {geometry.psr.standoff_m && geometry.psr.standoff_m < 10000
            ? `${geometry.psr.standoff_m.toLocaleString('en-US')} m to ${geometry.psr.nearest_name} (${geometry.psr.drill_range_viable ? 'PRIME-1 Viable' : 'Traverse Required'})`
            : `${geometry.psr.distance_km.toFixed(1)} km to ${geometry.psr.nearest_name} (${geometry.psr.drill_range_viable ? 'PRIME-1 Viable' : 'Traverse Required'})`}
        </p>

        <button type="button" className="site-map__back" onClick={onBack}>
          ◀ BACK TO GLOBAL FLEET
        </button>

        <div className="site-map__dock">
          <div className="site-map__hud">
            <p>
              {formatCoords(mission.lat, mission.lon)} &nbsp;|&nbsp; ELEVATION: +{mission.elevationM.toLocaleString('en-US')}m
              &nbsp;|&nbsp; MEAN SLOPE: {mission.slopeDeg.toFixed(1)}°
            </p>
            <p className="site-map__hud-dim">
              SCALE: ── 2 km ── &nbsp;|&nbsp; LOLA 20m DEM (LDEM_80S) &nbsp;|&nbsp; NAIF SPICE de430
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
              PDS DATA ↗
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
