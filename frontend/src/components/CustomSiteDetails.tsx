import { useState } from 'react'
import type { CustomLookup, CustomRequest, CustomSitePayload } from '../data/api'
import { formatCoords } from '../data/missions'
import { formatHours } from '../data/timeline'
import { fmtPct, horizonLabel } from '../data/tracks'
import { Icon } from './Icon'
import { PleaseWait } from './PleaseWait'
import './MissionDetails.css'

interface Props {
  request: CustomRequest
  lookup: CustomLookup
  onRetry: () => void
  onChangeUtc: (utc: string) => void
}

const UNAVAILABLE = 'Unavailable'

/** "2026-11-15T12:00:00Z" <-> "2026-11-15T12:00" for a datetime-local input read as UTC. */
const toInput = (utc: string) => utc.slice(0, 16)
const fromInput = (value: string) => `${value}:00Z`
const showUtc = (utc: string) => `${utc.slice(0, 16).replace('T', ' ')} UTC`

export function CustomSiteDetails({ request, lookup, onRetry, onChangeUtc }: Props) {
  const [draftUtc, setDraftUtc] = useState(toInput(request.utc))
  const changed = fromInput(draftUtc) !== request.utc

  return (
    <div className="details">
      <div className="details__block details__head">
        <p className="details__eyebrow details__eyebrow--icon">
          <Icon name="pin" size={14} />
          Custom point
        </p>
        <h2 className="details__title">{formatCoords(request.lat, request.lon)}</h2>
        <p className="details__sub">Computed live by the ApolloHarness engine from NASA SPICE and LOLA data.</p>
        <form
          className="details__time"
          onSubmit={(e) => {
            e.preventDefault()
            if (draftUtc) onChangeUtc(fromInput(draftUtc))
          }}
        >
          <label>
            <span>Start time (UTC)</span>
            <input type="datetime-local" value={draftUtc} onChange={(e) => setDraftUtc(e.target.value)} required />
          </label>
          <button type="submit" disabled={!changed || !draftUtc}>
            Recompute
          </button>
        </form>
      </div>

      {lookup.state === 'loading' && (
        <section className="details__block">
          <PleaseWait task="Calculating this point" live />
        </section>
      )}

      {lookup.state === 'error' && (
        <section className="details__block">
          <p className="details__status details__status--error">{lookup.reason}</p>
          <p className="details__note">Mission sites still work: their tracks are bundled with the site.</p>
          <button type="button" className="details__link" onClick={onRetry}>
            Try again
          </button>
        </section>
      )}

      {lookup.state === 'ready' && <Readout p={lookup.site.payload} />}
    </div>
  )
}

function Readout({ p }: { p: CustomSitePayload }) {
  const s = p.track_summary
  const bars = [
    { label: 'Sunlight over the window', value: fmtPct(s.sunlit_percent), fill: s.sunlit_percent },
    { label: 'Earth in view (radio contact)', value: fmtPct(s.earth_los_percent), fill: s.earth_los_percent },
    {
      label: 'Average share of Sun visible',
      value: fmtPct(s.mean_sun_disk_visible_fraction === null ? null : s.mean_sun_disk_visible_fraction * 100),
      fill: s.mean_sun_disk_visible_fraction === null ? null : s.mean_sun_disk_visible_fraction * 100,
    },
  ]
  const t = p.terrain
  const slope =
    t.regional_slope_deg == null
      ? UNAVAILABLE
      : `${t.regional_slope_deg.toFixed(1)}° over ${t.regional_slope_baseline_m != null ? `${Math.round(t.regional_slope_baseline_m).toLocaleString('en-US')} m` : 'the DEM baseline'}`
  const psr = p.psr
  const psrText =
    psr?.status === 'outside_product_coverage'
      ? 'Not covered (PSR map spans 80–90°S)'
      : !psr || psr.distance_km == null
        ? UNAVAILABLE
      : psr.inside_psr
        ? 'Inside a PSR'
        : `${psr.distance_km.toFixed(2)} km${psr.nearest_psr_label ? ` · ${psr.nearest_psr_label}` : ''}`
  const days = (p.track as { duration_days?: number }).duration_days ?? 29.5

  return (
    <>
      <section className="details__block">
        <div className="details__row">
          <h3 className="section-title">Light &amp; contact · {days} days</h3>
          <span className="badge" data-tone={p.horizon_model === 'lola_terrain_mask' ? 'ok' : 'warn'} title="Whether terrain was modelled for the horizon">
            <Icon name="mountain" />
            {horizonLabel(p.horizon_model)}
          </span>
        </div>
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
        <h3 className="section-title">Coming up · from {showUtc(p.utc)}</h3>
        {p.events.length === 0 ? (
          <p className="details__note">No sunrise, sunset, Earthrise or Earthset within the window.</p>
        ) : (
          <ul className="details__events">
            {p.events.map((ev) => (
              <li key={`${ev.body}-${ev.kind}-${ev.utc}`}>
                <span className="details__event-what" data-tone={ev.kind === 'rise' ? 'ok' : 'warn'}>
                  <Icon name={ev.kind === 'rise' ? 'rise' : 'set'} size={15} />
                  {ev.body === 'sun' ? (ev.kind === 'rise' ? 'Sunrise' : 'Sunset') : ev.kind === 'rise' ? 'Earthrise' : 'Earthset'}
                </span>
                <span className="details__event-when">
                  in {formatHours(ev.hours_from_start)}
                  <em>{showUtc(ev.utc)}</em>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="details__block">
        <h3 className="section-title">Site</h3>
        <div className="details__grid">
          <div className="stat">
            <span>Elevation</span>
            <strong>
              {t.elevation_m == null
                ? UNAVAILABLE
                : `${t.elevation_m >= 0 ? '+' : '−'}${Math.abs(Math.round(t.elevation_m)).toLocaleString('en-US')} m`}
            </strong>
          </div>
          <div className="stat">
            <span>Terrain slope (regional)</span>
            <strong>{slope}</strong>
          </div>
          <div className="stat">
            <span>Nearest shadowed crater</span>
            <strong>{psrText}</strong>
          </div>
          <div className="stat">
            <span>Round trip to Earth</span>
            <strong>{p.earth.round_trip_light_time_s == null ? UNAVAILABLE : `${p.earth.round_trip_light_time_s.toFixed(2)} s`}</strong>
          </div>
        </div>
        <p className="details__note">
          A point you chose, not a mission site. The slope describes the landscape over the DEM baseline, not the ground
          under a lander's feet.
        </p>
      </section>

      <section className="details__block details__block--provenance">
        <h3 className="section-title">Sources</h3>
        <div className="details__prov">
          <p>Sun and Earth geometry: NASA/JPL NAIF SPICE ephemeris</p>
          <p>Terrain: {t.dem_product ?? UNAVAILABLE}</p>
          {psr?.status === 'complete' && <p>Shadowed craters: NASA LRO LOLA PSR product</p>}
        </div>
      </section>
    </>
  )
}
