import {
  categoryLabel,
  formatCoords,
  psrFill,
  scoreTag,
  type Mission,
} from '../data/missions'
import './MissionDetails.css'

interface MissionDetailsProps {
  mission: Mission
  onCompare: () => void
  onOpenProvenance: () => void
  /** Offered only for missions that have a zoomed site view. */
  onOpenInspector?: () => void
}

const PROVENANCE = [
  'ELEVATION: NASA LRO LOLA (20m Polar DEM)',
  'LIGHTING: NASA LROC WAC (Mazarico et al. 2011)',
  'ORBITS: NASA JPL NAIF SPICE de421.bsp',
]

export function MissionDetails({ mission, onCompare, onOpenProvenance, onOpenInspector }: MissionDetailsProps) {
  const v = mission.viability
  const bars = [
    { label: '01. MISSION WINDOW SUNLIGHT', value: `${v.windowSunlight.toFixed(1)}%`, fill: v.windowSunlight },
    { label: '02. ANNUAL SUNLIGHT BASELINE', value: `${v.annualSunlight.toFixed(1)}%`, fill: v.annualSunlight },
    { label: '03. EARTH COMMS LINE-OF-SIGHT', value: `${v.commsLos.toFixed(1)}% LOS`, fill: v.commsLos },
    { label: '04. DISTANCE TO PSR COLD TRAP', value: `${v.psrKm.toFixed(1)} km`, fill: psrFill(v.psrKm) },
  ]

  return (
    <div className="details">
      <div className="details__block details__head">
        <p className="details__eyebrow">SELECTED SITE</p>
        <h2 className="details__title">{mission.name}</h2>
        <p className="details__sub">
          {mission.provider} · {mission.target}
        </p>
      </div>

      <section className="details__block">
        <p className="section-title">01 // MISSION PROFILE</p>
        <dl className="details__meta">
          <div>
            <dt>PROVIDER</dt>
            <dd>{mission.provider}</dd>
          </div>
          <div>
            <dt>LANDER</dt>
            <dd>{mission.lander}</dd>
          </div>
          <div>
            <dt>LAUNCH WINDOW</dt>
            <dd>{mission.launchWindow}</dd>
          </div>
          <div>
            <dt>TARGET</dt>
            <dd>{mission.site}</dd>
          </div>
        </dl>
      </section>

      <section className="details__block">
        <div className="details__row">
          <p className="section-title">02 // ENVIRONMENTAL VIABILITY INDEX</p>
          <span className="badge">{scoreTag(mission.score)}</span>
        </div>
        <p className="details__score">
          {mission.score}
          <span> / 100</span>
        </p>
        {mission.dataStatus === 'placeholder' && (
          <p className="details__note" title="Illustrative values until PDS-derived numbers are wired in">
            PROVISIONAL · ILLUSTRATIVE VALUES
          </p>
        )}
        <div className="details__bars">
          {bars.map((bar) => (
            <div key={bar.label}>
              <div className="details__metric">
                <span>{bar.label}</span>
                <span>{bar.value}</span>
              </div>
              <div className="bar">
                <div className="bar__fill" style={{ width: `${bar.fill}%` }} />
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="details__block">
        <p className="section-title">03 // SITE GEOMETRY</p>
        <div className="details__grid">
          <Stat label="LANDING ELLIPSE" value={`${mission.ellipseKm[0] * 2}km × ${mission.ellipseKm[1] * 2}km`} />
          <Stat label="TERRAIN SLOPE" value={`${mission.slopeDeg.toFixed(1)}° (nominal)`} />
          <Stat
            label="ELEVATION"
            value={`${mission.elevationM >= 0 ? '+' : '−'}${Math.abs(mission.elevationM).toLocaleString('en-US')}m`}
          />
          <Stat label="LAT / LON" value={formatCoords(mission.lat, mission.lon)} />
        </div>
      </section>

      <section className="details__block">
        <p className="section-title">04 // PAYLOAD MANIFEST (CLPS)</p>
        <div className="details__payloads">
          {mission.payloads.map((p) => (
            <div className="payload" key={p.name}>
              <div className="payload__top">
                <strong>{p.name}</strong>
                <span className={`tag tag--${p.category}`}>{categoryLabel[p.category]}</span>
              </div>
              <span>{p.detail}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="details__block details__block--provenance">
        <p className="section-title">05 // SCIENTIFIC PROVENANCE (NASA PDS)</p>
        <div className="details__prov">
          {PROVENANCE.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
        <button type="button" className="details__link" onClick={onOpenProvenance}>
          [ View Raw PDS Data &amp; Curves ↗ ]
        </button>
      </section>

      <div className="details__cta">
        {onOpenInspector && (
          <button type="button" className="details__cta-secondary" onClick={onOpenInspector}>
            [ OPEN SITE INSPECTOR ]
          </button>
        )}
        <button type="button" onClick={onCompare}>
          [ COMPARE SITES ]
        </button>
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}
