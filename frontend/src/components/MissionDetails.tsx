import {
  categoryLabel,
  coordinateBadge,
  formatCoords,
  humanize,
  isLocated,
  type Mission,
} from '../data/missions'
import { fmtPct, useTrack } from '../data/tracks'
import './MissionDetails.css'

interface MissionDetailsProps {
  mission: Mission
  onCompare: () => void
  onOpenProvenance: () => void
  /** Offered only for missions that have a zoomed site view. */
  onOpenInspector?: () => void
}

const UNAVAILABLE = 'Unavailable'

export function MissionDetails({ mission, onCompare, onOpenProvenance, onOpenInspector }: MissionDetailsProps) {
  const lookup = useTrack(mission.id)
  const data = lookup.state === 'ready' ? lookup.data : null
  const track = data?.track ?? null

  const bars = [
    { label: '01. WINDOW SUNLIGHT', value: fmtPct(track?.sunlit_percent), fill: track?.sunlit_percent ?? null },
    { label: '02. EARTH COMMS LINE-OF-SIGHT', value: fmtPct(track?.earth_los_percent), fill: track?.earth_los_percent ?? null },
    {
      label: '03. MEAN SUN DISC VISIBLE',
      value: fmtPct(track && track.mean_sun_disk_visible_fraction !== null ? track.mean_sun_disk_visible_fraction * 100 : null),
      fill: track && track.mean_sun_disk_visible_fraction !== null ? track.mean_sun_disk_visible_fraction * 100 : null,
    },
  ]

  const ellipse =
    mission.ellipseMajorKm !== null && mission.ellipseMinorKm !== null
      ? `${mission.ellipseMajorKm} km × ${mission.ellipseMinorKm} km`
      : mission.ellipseMajorKm !== null
        ? `${mission.ellipseMajorKm} km major axis (minor not published)`
        : 'Not published'

  const psr = data?.psr
  const psrText =
    psr?.distance_km === null || psr?.distance_km === undefined
      ? UNAVAILABLE
      : psr.inside_psr
        ? 'Inside a PSR'
        : `${psr.distance_km.toFixed(2)} km`

  return (
    <div className="details">
      <div className="details__block details__head">
        <p className="details__eyebrow">{mission.kind === 'reference_anchor' ? 'REFERENCE ANCHOR' : 'SELECTED SITE'}</p>
        <h2 className="details__title">{mission.name}</h2>
        <p className="details__sub">
          {mission.provider} · {mission.targetSite}
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
            <dt>TARGET DATE</dt>
            <dd>{mission.targetDate ?? 'TBD'}</dd>
          </div>
          <div>
            <dt>STATUS</dt>
            <dd>{humanize(mission.status)}</dd>
          </div>
        </dl>
        {mission.statusNote && <p className="details__note">{mission.statusNote}</p>}
      </section>

      <section className="details__block">
        <div className="details__row">
          <p className="section-title">02 // ILLUMINATION &amp; COMMS (29.5-DAY WINDOW)</p>
          {track && (
            <span className="badge" title="Whether terrain was modelled for the horizon">
              {track.horizon_model === 'lola_terrain_mask' ? 'LOLA TERRAIN HORIZON' : 'SPHERICAL HORIZON'}
            </span>
          )}
        </div>
        {lookup.state === 'loading' && <p className="details__note">LOADING TRACK…</p>}
        {(lookup.state === 'none' || lookup.state === 'error') && (
          <p className="details__note">UNAVAILABLE · {lookup.reason}</p>
        )}
        <div className="details__bars">
          {bars.map((bar) => (
            <div key={bar.label}>
              <div className="details__metric">
                <span>{bar.label}</span>
                <span>{bar.value}</span>
              </div>
              <div className="bar">
                <div className="bar__fill" style={{ width: `${bar.fill ?? 0}%` }} />
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="details__block">
        <p className="section-title">03 // SITE GEOMETRY</p>
        <div className="details__grid">
          <Stat label="LANDING ELLIPSE" value={ellipse} />
          <Stat
            label="ELEVATION"
            value={
              data?.terrain.elevation_m == null
                ? UNAVAILABLE
                : `${data.terrain.elevation_m >= 0 ? '+' : '−'}${Math.abs(Math.round(data.terrain.elevation_m)).toLocaleString('en-US')}m`
            }
          />
          <Stat label="NEAREST PSR" value={psrText} />
          <Stat label="LAT / LON" value={isLocated(mission) ? formatCoords(mission.lat, mission.lon) : 'No coordinate published'} />
        </div>
        <p className="details__note" title={mission.coordinateProvenance}>
          {coordinateBadge(mission)} · {humanize(mission.coordinateType)}
        </p>
        <p className="details__note">{mission.coordinateProvenance}</p>
      </section>

      <section className="details__block">
        <p className="section-title">04 // PAYLOAD MANIFEST</p>
        <div className="details__payloads">
          {mission.payloads.map((p) => (
            <div className="payload" key={p.name}>
              <div className="payload__top">
                <strong>{p.name}</strong>
                <span className={`tag tag--${p.category}`}>{categoryLabel[p.category]}</span>
              </div>
              <span>{p.purpose.map((x) => x.replace(/_/g, ' ')).join(' · ')}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="details__block details__block--provenance">
        <p className="section-title">05 // SOURCES</p>
        <div className="details__prov">
          {data?.terrain.dem_product && <p>TERRAIN: {data.terrain.dem_product}</p>}
          {mission.sources.map((s) => (
            <p key={s.url}>
              <a href={s.url} target="_blank" rel="noreferrer">
                {s.publisher}: {s.title}
              </a>
            </p>
          ))}
        </div>
        <button type="button" className="details__link" onClick={onOpenProvenance}>
          [ View Data Provenance ↗ ]
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
