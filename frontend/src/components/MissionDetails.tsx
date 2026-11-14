import {
  categoryLabel,
  coordinateBadge,
  formatCoords,
  humanize,
  isLocated,
  type Mission,
} from '../data/missions'
import { fmtPct, horizonLabel, useTrack } from '../data/tracks'
import { Icon } from './Icon'
import './MissionDetails.css'

interface MissionDetailsProps {
  mission: Mission
  onCompare: () => void
  onOpenProvenance: () => void
  /** Offered only for missions that have a zoomed site view. */
  onOpenInspector?: () => void
}

const UNAVAILABLE = 'Unavailable'

const CATEGORY_ICON = { volatiles: 'droplet', spectrometers: 'spectrum', rovers: 'rover', other: 'gauge' } as const

export function MissionDetails({ mission, onCompare, onOpenProvenance, onOpenInspector }: MissionDetailsProps) {
  const lookup = useTrack(mission.id)
  const data = lookup.state === 'ready' ? lookup.data : null
  const track = data?.track ?? null

  const bars = [
    { label: 'Sunlight over the window', value: fmtPct(track?.sunlit_percent), fill: track?.sunlit_percent ?? null },
    { label: 'Earth in view (radio contact)', value: fmtPct(track?.earth_los_percent), fill: track?.earth_los_percent ?? null },
    {
      label: 'Average share of Sun visible',
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
    psr?.status === 'outside_product_coverage'
      ? 'Not covered (PSR map spans 80–90°S)'
      : psr?.distance_km === null || psr?.distance_km === undefined
        ? UNAVAILABLE
      : psr.inside_psr
        ? 'Inside a PSR'
        : `${psr.distance_km.toFixed(2)} km`

  return (
    <div className="details">
      <div className="details__block details__head">
        <p className="details__eyebrow">{mission.kind === 'reference_anchor' ? 'Reference landing' : 'CLPS mission'}</p>
        <h2 className="details__title">{mission.name}</h2>
        <p className="details__sub">
          {mission.provider} · {mission.targetSite}
        </p>
      </div>

      <section className="details__block">
        <h3 className="section-title">Mission</h3>
        <dl className="details__meta">
          <div>
            <dt>Provider</dt>
            <dd>{mission.provider}</dd>
          </div>
          <div>
            <dt>Lander</dt>
            <dd>{mission.lander}</dd>
          </div>
          <div>
            <dt>Target date</dt>
            <dd>{mission.targetDate ?? 'TBD'}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{humanize(mission.status)}</dd>
          </div>
        </dl>
        {mission.touchdownUtc && (
          <p className="details__note">Touchdown {mission.touchdownUtc.replace('T', ' ').replace('Z', '')} UTC</p>
        )}
        {mission.baselineRole && (
          <p className="details__note">
            {humanize(mission.baselineRole.tag.replace(/_baseline$/, ''))} baseline: {mission.baselineRole.text}
          </p>
        )}
        {mission.statusNote && <p className="details__note">{mission.statusNote}</p>}
      </section>

      <section className="details__block">
        <div className="details__row">
          <h3 className="section-title">Light &amp; contact · 29.5 days</h3>
          {track && (
            <span
              className="badge"
              data-tone={track.horizon_model === 'lola_terrain_mask' ? 'ok' : 'warn'}
              title="Whether terrain was modelled for the horizon"
            >
              <Icon name="mountain" />
              {horizonLabel(track.horizon_model)}
            </span>
          )}
        </div>
        {lookup.state === 'loading' && <p className="details__note">Loading track…</p>}
        {(lookup.state === 'none' || lookup.state === 'error') && (
          <p className="details__note">Unavailable: {lookup.reason}</p>
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
        <h3 className="section-title">Site</h3>
        <div className="details__grid">
          <Stat label="Landing ellipse" value={ellipse} />
          <Stat
            label="Elevation"
            value={
              data?.terrain.elevation_m == null
                ? UNAVAILABLE
                : `${data.terrain.elevation_m >= 0 ? '+' : '−'}${Math.abs(Math.round(data.terrain.elevation_m)).toLocaleString('en-US')}m`
            }
          />
          <Stat label="Nearest shadowed crater" value={psrText} />
          <Stat label="Coordinates" value={isLocated(mission) ? formatCoords(mission.lat, mission.lon) : 'No coordinate published'} />
        </div>
        <p className="details__note" title={mission.coordinateProvenance}>
          {coordinateBadge(mission)} · {humanize(mission.coordinateType)}
        </p>
        <p className="details__note">{mission.coordinateProvenance}</p>
      </section>

      <section className="details__block">
        <h3 className="section-title">Payloads</h3>
        <div className="details__payloads">
          {mission.payloads.map((p) => (
            <div className="payload" key={p.name}>
              <div className="payload__top">
                <strong>{p.name}</strong>
                <span className={`tag tag--${p.category}`}>
                  <Icon name={CATEGORY_ICON[p.category]} size={14} />
                  {categoryLabel[p.category]}
                </span>
              </div>
              <span>{p.purpose.map((x) => x.replace(/_/g, ' ')).join(' · ')}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="details__block details__block--provenance">
        <h3 className="section-title">Sources</h3>
        <div className="details__prov">
          {data?.terrain.dem_product && <p>Terrain: {data.terrain.dem_product}</p>}
          {mission.sources.map((s) => (
            <p key={s.url}>
              <a href={s.url} target="_blank" rel="noreferrer">
                {s.publisher}: {s.title}
              </a>
            </p>
          ))}
        </div>
        <button type="button" className="details__link" onClick={onOpenProvenance}>
          View data provenance →
        </button>
      </section>

      <div className="details__cta">
        {onOpenInspector && (
          <button type="button" className="details__cta-secondary" onClick={onOpenInspector}>
            Open site inspector
          </button>
        )}
        <button type="button" onClick={onCompare}>
          Compare sites
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
