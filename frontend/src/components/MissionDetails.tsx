import { useEffect, useState } from 'react'
import {
  categoryLabel,
  formatCoords,
  psrFill,
  scoreTag,
  type Mission,
} from '../data/missions'
import {
  fetchGeometryV1,
  fetchSiteComms,
  fetchSiteScore,
  fetchSiteSensitivity,
  type GeometryV1Response,
  type SiteCommsResponse,
  type SiteScoreResponse,
  type SiteSensitivityResponse,
} from '../services/api'
import type { UIMode } from './Header'
import './MissionDetails.css'

interface MissionDetailsProps {
  mission: Mission
  onCompare: () => void
  onOpenProvenance: () => void
  onOpenInspector?: () => void
  uiMode?: UIMode
}

const PROVENANCE = [
  'CELESTIAL EPHEMERIS: NASA NAIF SPICE de430.bsp + moon_pa/me',
  'LUNAR TOPOGRAPHY: LOLA 20m/80m DEM GeoTIFF (LDEM_80S_80MPP)',
  'DECENNIAL ILLUMINATION: LROC/LOLA PGDA Product 69 (18.6-yr cycle)',
  'CRYOGENIC COLD TRAPS: 506,349 Permanently Shadowed Regions (<110K)',
]

export function MissionDetails({
  mission,
  onCompare,
  onOpenProvenance,
  onOpenInspector,
  uiMode = 'simple',
}: MissionDetailsProps) {
  const [liveScore, setLiveScore] = useState<SiteScoreResponse | null>(null)
  const [liveComms, setLiveComms] = useState<SiteCommsResponse | null>(null)
  const [geometry, setGeometry] = useState<GeometryV1Response | null>(null)
  const [sensitivity, setSensitivity] = useState<SiteSensitivityResponse | null>(null)
  const [loadingSensitivity, setLoadingSensitivity] = useState(false)
  const [sensitivityNote, setSensitivityNote] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    if (uiMode !== 'scientific') return

    if (mission.lat > -83.5) {
      setSensitivity(null)
      setSensitivityNote(
        'Polar micro-terrain sensitivity analysis applies to south polar sites (83.5°S – 90.0°S). Non-polar sites follow standard 14-day synodic day/night cycles without local ridge shadowing.'
      )
      return
    }

    setLoadingSensitivity(true)
    setSensitivityNote(null)

    fetchSiteSensitivity({
      lat: mission.lat,
      lon: mission.lon,
      utc: mission.start_date || '2026-11-15T12:00:00Z',
      siteId: mission.id,
    })
      .then((res) => {
        if (!active) return
        if (res) {
          setSensitivity(res)
          setSensitivityNote(null)
        } else {
          setSensitivity(null)
          setSensitivityNote('High-resolution sensitivity evaluation unavailable.')
        }
      })
      .catch(() => {
        if (active) {
          setSensitivity(null)
          setSensitivityNote('Sensitivity evaluation unavailable.')
        }
      })
      .finally(() => {
        if (active) setLoadingSensitivity(false)
      })

    return () => {
      active = false
    }
  }, [mission.lat, mission.lon, mission.start_date, mission.id, uiMode])

  useEffect(() => {
    let active = true
    fetchSiteScore(mission.lat, mission.lon, mission.start_date, mission.end_date).then((res) => {
      if (active) setLiveScore(res)
    })
    fetchSiteComms(mission.lat, mission.lon, mission.start_date, mission.end_date).then((res) => {
      if (active) setLiveComms(res)
    })
    fetchGeometryV1({
      site_id: mission.id,
      lat: mission.lat,
      lon: mission.lon,
      utc: mission.start_date,
    }).then((res) => {
      if (active && res) setGeometry(res)
    })
    return () => {
      active = false
    }
  }, [mission.id, mission.lat, mission.lon, mission.start_date, mission.end_date])

  const v = mission.viability || {
    windowSunlight: 75.0,
    annualSunlight: 50.0,
    commsLos: 80.0,
    psrKm: 2.5,
  }
  const displayedScore =
    liveScore?.viability_score != null
      ? Math.round(liveScore.viability_score)
      : (mission.score ?? 75)
  const tacticalSunPct =
    liveScore?.tactical_mission_sunlight_percent ?? v.windowSunlight ?? 75.0
  const annualSunPct = v.annualSunlight ?? 50.0
  const commsUptimePct =
    liveComms?.communications_uptime_percent ??
    liveScore?.comms_uptime_percent ??
    v.commsLos ??
    80.0
  const psrDistKm = liveScore?.psr_distance_km ?? v.psrKm ?? 2.5

  const sunCountdown =
    geometry?.sun?.time_to_sunset_formatted
      ? `${geometry.sun.time_to_sunset_formatted} of sunlight remaining`
      : geometry?.sun?.is_lit
        ? 'Continuous sunlight window'
        : 'Night cycle active'

  const pingStr = geometry?.earth?.round_trip_light_time_s
    ? `${geometry.earth.round_trip_light_time_s.toFixed(2)} s`
    : '2.56 s'
  const earthStatus = geometry?.earth?.direct_los
    ? `ACTIVE (round-trip ping ${pingStr})`
    : 'OCCULTED'

  const sunDiscPct = geometry?.sun?.disk_visible_fraction != null
    ? Math.round(geometry.sun.disk_visible_fraction * 100)
    : 100
  const earthDiscPct = geometry?.earth?.disk_visible_fraction != null
    ? Math.round(geometry.earth.disk_visible_fraction * 100)
    : 100

  const sunMargin =
    geometry?.sun?.elevation_deg != null && geometry?.sun?.terrain_horizon_deg != null
      ? (geometry.sun.elevation_deg - geometry.sun.terrain_horizon_deg).toFixed(2)
      : '+0.07'
  const earthMargin =
    geometry?.earth?.elevation_deg != null && geometry?.earth?.terrain_horizon_deg != null
      ? (geometry.earth.elevation_deg - geometry.earth.terrain_horizon_deg).toFixed(2)
      : '+2.90'

  const bars = [
    { label: '01. MISSION WINDOW SUNLIGHT', value: `${tacticalSunPct.toFixed(1)}%`, fill: tacticalSunPct },
    { label: '02. ANNUAL SUNLIGHT BASELINE', value: `${annualSunPct.toFixed(1)}%`, fill: annualSunPct },
    { label: '03. EARTH COMMS LINE-OF-SIGHT', value: `${commsUptimePct.toFixed(1)}% LOS`, fill: commsUptimePct },
    { label: '04. DISTANCE TO PSR COLD TRAP', value: `${psrDistKm.toFixed(1)} km`, fill: psrFill(psrDistKm) },
  ]

  return (
    <div className="details">
      <div className="details__block details__head">
        <div className="details__head-meta">
          <p className="details__eyebrow">SELECTED SITE</p>
          <span className={`mode-tag mode-tag--${uiMode}`}>
            {uiMode === 'simple' ? 'CLASSROOM / PUBLIC MODE' : 'SCIENTIFIC FLIGHT DYNAMICS'}
          </span>
        </div>
        <h2 className="details__title">{mission.name}</h2>
        <p className="details__sub">
          {mission.provider} · {mission.target}
        </p>
      </div>

      {/* A1. SIMPLE MODE: SURVIVAL COUNTDOWNS & PLAIN-LANGUAGE BADGES */}
      {uiMode === 'simple' && (
        <section className="details__block details__block--simple-hud">
          <p className="section-title">OPERATIONAL COUNTDOWNS &amp; SAFETY</p>

          <div className="countdown-card">
            <div className="countdown-card__row">
              <span className="countdown-icon">☀️</span>
              <div>
                <strong className="countdown-label">SOLAR SURVIVAL CLOCK</strong>
                <p className="countdown-value">{sunCountdown}</p>
              </div>
            </div>
            <div className="countdown-card__row">
              <span className="countdown-icon">📡</span>
              <div>
                <strong className="countdown-label">DIRECT EARTH CONTACT</strong>
                <p className={`countdown-value ${geometry?.earth?.direct_los ? 'countdown-value--cyan' : 'countdown-value--warn'}`}>
                  {earthStatus}
                </p>
              </div>
            </div>
          </div>

          <div className="plain-badges">
            <div className="plain-badge">
              <span className="plain-badge__title">SOLAR POWER</span>
              <strong className={`plain-badge__tag ${geometry?.sun?.is_lit ? 'tag--ok' : 'tag--warn'}`}>
                {geometry?.sun?.is_lit
                  ? sunDiscPct >= 99
                    ? 'OPTIMAL (Full Sun)'
                    : `PARTIAL (${sunDiscPct}% visible)`
                  : 'CRITICAL_BLACKOUT'}
              </strong>
            </div>
            <div className="plain-badge">
              <span className="plain-badge__title">RADIO LINK</span>
              <strong className={`plain-badge__tag ${geometry?.earth?.direct_los ? 'tag--cyan' : 'tag--fail'}`}>
                {geometry?.earth?.direct_los ? 'CONNECTED' : 'OCCULTED'}
              </strong>
            </div>
            <div className="plain-badge">
              <span className="plain-badge__title">LANDER FOOTING</span>
              <strong className="plain-badge__tag tag--ok">
                SAFE ({typeof mission.slopeDeg === 'number' ? `${mission.slopeDeg.toFixed(1)}° slope` : 'nominal'})
              </strong>
            </div>
          </div>
        </section>
      )}

      {/* A2. SCIENTIFIC MODE: PRECISION TOPOCENTRIC EPHEMERIS TELEMETRY */}
      {uiMode === 'scientific' && (
        <section className="details__block details__block--scientific">
          <p className="section-title">PRECISION EPHEMERIS &amp; TOPOGRAPHY (SPICE / LOLA)</p>

          <div className="telemetry-table-wrapper">
            <table className="telemetry-table">
              <thead>
                <tr>
                  <th>BODY</th>
                  <th>ELEV</th>
                  <th>AZIMUTH</th>
                  <th>HORIZON</th>
                  <th>MARGIN</th>
                  <th>DISC</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="cell--highlight">SUN (☉)</td>
                  <td>{geometry?.sun?.elevation_deg != null ? `${geometry.sun.elevation_deg >= 0 ? '+' : ''}${geometry.sun.elevation_deg.toFixed(2)}°` : 'N/A'}</td>
                  <td>{geometry?.sun?.azimuth_deg != null ? `${geometry.sun.azimuth_deg.toFixed(1)}°` : 'N/A'}</td>
                  <td>{geometry?.sun?.terrain_horizon_deg != null ? `${geometry.sun.terrain_horizon_deg >= 0 ? '+' : ''}${geometry.sun.terrain_horizon_deg.toFixed(2)}°` : 'N/A'}</td>
                  <td className="cell--cyan">{sunMargin >= '0' ? `+${sunMargin}°` : `${sunMargin}°`}</td>
                  <td>{sunDiscPct}%</td>
                </tr>
                <tr>
                  <td className="cell--highlight">EARTH (⊕)</td>
                  <td>{geometry?.earth?.elevation_deg != null ? `${geometry.earth.elevation_deg >= 0 ? '+' : ''}${geometry.earth.elevation_deg.toFixed(2)}°` : 'N/A'}</td>
                  <td>{geometry?.earth?.azimuth_deg != null ? `${geometry.earth.azimuth_deg.toFixed(1)}°` : 'N/A'}</td>
                  <td>{geometry?.earth?.terrain_horizon_deg != null ? `${geometry.earth.terrain_horizon_deg >= 0 ? '+' : ''}${geometry.earth.terrain_horizon_deg.toFixed(2)}°` : 'N/A'}</td>
                  <td className="cell--cyan">{earthMargin >= '0' ? `+${earthMargin}°` : `${earthMargin}°`}</td>
                  <td>{earthDiscPct}%</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="unit-vectors-box">
            <span className="vectors-title">UNIT VECTORS (FRAME: MOON_PA)</span>
            <code>☉ SUN:   [{geometry?.sun?.unit_vector_moon_pa?.map((n) => n.toFixed(4)).join(', ') || 'N/A'}]</code>
            <code>⊕ EARTH: [{geometry?.earth?.unit_vector_moon_pa?.map((n) => n.toFixed(4)).join(', ') || 'N/A'}]</code>
          </div>

          <div className="scientific-meta">
            <span>HORIZON MODEL: <strong>{geometry?.horizon_model || 'lola_terrain_mask'}</strong></span>
            <span>DEM PRODUCT: <strong>{geometry?.terrain?.dem_product || 'LOLA LDEM_80S_80MPP_ADJ'}</strong></span>
          </div>

          {/* A2.2 LOCAL POSITION SENSITIVITY & 1-KM NEIGHBOUR OPTIMIZATION */}
          <div className="sensitivity-section">
            <span className="vectors-title">LOCAL TERRAIN SENSITIVITY (±1 KM)</span>
            {loadingSensitivity ? (
              <div className="sensitivity-loading">Analyzing LOLA micro-relief &amp; slip curves...</div>
            ) : sensitivityNote ? (
              <div className="sensitivity-note">{sensitivityNote}</div>
            ) : sensitivity ? (
              <>
                <div className="sensitivity-headline-card">
                  <div className="sensitivity-headline-title">OPTIMIZATION HEADLINE</div>
                  <div className="sensitivity-headline-text">
                    {sensitivity.position?.sunlit_percent?.headline ||
                      (sensitivity.position?.sunlit_percent?.centre_is_best
                        ? `Current site is a local illumination optimum within 1 km (${sensitivity.position.sunlit_percent.centre.toFixed(1)}% sunlight).`
                        : sensitivity.position?.sunlit_percent?.best_neighbour
                          ? `Moving ${Math.round(sensitivity.position.sunlit_percent.best_neighbour.distance_m)} m ${sensitivity.position.sunlit_percent.best_neighbour.direction} raises sunlight from ${sensitivity.position.sunlit_percent.centre.toFixed(1)}% to ${sensitivity.position.sunlit_percent.best_neighbour.value.toFixed(1)}% (slope ${sensitivity.position.sunlit_percent.best_neighbour.regional_slope_deg.toFixed(1)}°).`
                          : 'Local 1-km terrain evaluated.')}
                  </div>
                  {sensitivity.position?.sunlit_percent?.best_neighbour && (
                    <div className="sensitivity-neighbour-detail">
                      <span>BEARING: {sensitivity.position.sunlit_percent.best_neighbour.bearing_deg.toFixed(1)}° ({sensitivity.position.sunlit_percent.best_neighbour.direction})</span>
                      <span>DISTANCE: {Math.round(sensitivity.position.sunlit_percent.best_neighbour.distance_m)} m</span>
                      <span>LOCAL SLOPE: {sensitivity.position.sunlit_percent.best_neighbour.regional_slope_deg.toFixed(1)}°</span>
                    </div>
                  )}
                </div>

                {/* A2.3 LAUNCH SLIP SENSITIVITY (±7-DAY ARRIVAL WINDOW) */}
                {sensitivity.arrival_date && sensitivity.arrival_date.length > 0 && (
                  <div className="arrival-slips-card">
                    <span className="vectors-title">LAUNCH SLIP SENSITIVITY (±7-DAY ARRIVAL WINDOW)</span>
                    <div className="telemetry-table-wrapper">
                      <table className="telemetry-table sensitivity-table">
                        <thead>
                          <tr>
                            <th>OFFSET</th>
                            <th>ARRIVAL (UTC)</th>
                            <th>SUNLIGHT</th>
                            <th>EARTH LOS</th>
                            <th>ARRIVAL STATE</th>
                          </tr>
                        </thead>
                        <tbody>
                          {sensitivity.arrival_date.map((slip) => {
                            const isNominal = slip.slip_days === 0
                            const offsetStr = isNominal ? 'NOMINAL (0d)' : `${slip.slip_days > 0 ? '+' : ''}${slip.slip_days}d`
                            const dateStr = slip.start_utc.slice(0, 10)
                            return (
                              <tr key={slip.slip_days} className={isNominal ? 'row--nominal' : undefined}>
                                <td className={isNominal ? 'cell--nominal-tag' : undefined}>{offsetStr}</td>
                                <td>{dateStr}</td>
                                <td className="cell--highlight">{slip.sunlit_percent.toFixed(1)}%</td>
                                <td className="cell--cyan">{slip.earth_los_percent.toFixed(1)}%</td>
                                <td>
                                  <span className={`slip-state ${slip.lit_at_arrival ? 'slip-state--lit' : 'slip-state--dark'}`}>
                                    {slip.lit_at_arrival ? '☀️ LIT' : '🌑 DARK'}
                                  </span>{' '}
                                  <span className={`slip-state ${slip.earth_visible_at_arrival ? 'slip-state--dte' : 'slip-state--blackout'}`}>
                                    {slip.earth_visible_at_arrival ? '📡 LOS' : '❌ OCC'}
                                  </span>
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </>
            ) : null}
          </div>
        </section>
      )}

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
          <span className="badge">{scoreTag(displayedScore)}</span>
        </div>
        <p className="details__score">
          {displayedScore}
          <span> / 100</span>
        </p>
        <p
          className={`details__note ${liveScore?.data_mode === 'mock' ? 'details__note--offline' : 'details__note--live'}`}
          title="Compute backend status"
        >
          {liveScore?.data_mode === 'mock'
            ? '⚠ OFFLINE DEMO MODE · NASA PDS ARCHIVAL CACHE'
            : liveScore
              ? '✓ FASTAPI COMPUTE · DETERMINISTIC PDS EVALUATION'
              : 'OFFLINE CACHED FIXTURES · NASA PDS ARCHIVE'}
        </p>
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

      <section className="details__block details__block--decision-gates">
        <p className="section-title">03 // OPERATIONAL DECISION GATES (PLATE 03)</p>

        {/* USE CASE 01: SOLAR HARD GATE */}
        <div className="gate-card">
          <div className="gate-card__head">
            <span className="gate-card__tag">UC-01</span>
            <strong className="gate-card__title">SOLAR HARD GATE</strong>
            <span
              className={`gate-badge ${
                tacticalSunPct > 0 ? 'gate-badge--ok' : 'gate-badge--fail'
              }`}
            >
              {tacticalSunPct > 0 ? 'PASSED (> 0%)' : 'HARD GATE TRIGGERED'}
            </span>
          </div>
          <div className="gate-card__body">
            <div className="gate-card__metric">
              <span>TACTICAL SUNLIGHT</span>
              <strong>{tacticalSunPct.toFixed(1)}%</strong>
            </div>
            <p className="gate-card__rule">
              {tacticalSunPct > 0
                ? `Viable Score: ${displayedScore}/100 [0.40Sun + 0.35DTE + 0.25Ice]`
                : 'Score Forced to 0.0: Solar Fatal Loss (0% Illumination)'}
            </p>
          </div>
        </div>

        {/* USE CASE 02: DTE LIBRATION COMMS */}
        <div className="gate-card">
          <div className="gate-card__head">
            <span className="gate-card__tag">UC-02</span>
            <strong className="gate-card__title">DTE LIBRATION COMMS</strong>
            <span
              className={`gate-badge ${
                commsUptimePct > 0 ? 'gate-badge--cyan' : 'gate-badge--fail'
              }`}
            >
              {commsUptimePct > 0 ? 'LINK CONNECTED' : 'OCCULTED'}
            </span>
          </div>
          <div className="gate-card__body">
            <div className="gate-card__metric">
              <span>DTE LOS AVAILABILITY</span>
              <strong>
                {commsUptimePct.toFixed(1)}% · RTT ~2.56s
                {liveComms?.avg_elevation_deg != null
                  ? ` (Avg Elev: +${liveComms.avg_elevation_deg.toFixed(1)}°)`
                  : ''}
              </strong>
            </div>
            <p className="gate-card__rule">
              {commsUptimePct > 0
                ? 'Nominal line-of-sight to Earth; Libration within horizon mask'
                : 'Alert: 14.5 hr Loss (Terrain occultation / Libration wobble)'}
            </p>
          </div>
        </div>

        {/* USE CASE 03: VOLATILE DRILL TARGETING */}
        <div className="gate-card">
          <div className="gate-card__head">
            <span className="gate-card__tag">UC-03</span>
            <strong className="gate-card__title">VOLATILE DRILL TARGETING</strong>
            <span
              className={`gate-badge ${
                psrDistKm < 3.0 ? 'gate-badge--ok' : 'gate-badge--warn'
              }`}
            >
              {psrDistKm < 3.0 ? 'OPTIMAL DRILL TARGET' : 'TRAVERSE REQUIRED'}
            </span>
          </div>
          <div className="gate-card__body">
            <div className="gate-card__metric">
              <span>STANDOFF TO COLD TRAP</span>
              <strong>
                {psrDistKm < 10.0
                  ? `${Math.round(psrDistKm * 1000).toLocaleString('en-US')} m standoff`
                  : `${psrDistKm.toFixed(1)} km standoff`}
              </strong>
            </div>
            <p className="gate-card__rule">
              {psrDistKm < 3.0
                ? 'PRIME-1 Viable · TRIDENT Drill Range (<3.0 km Standoff)'
                : 'Deep Shadow Standoff (≥3.0 km) · Autonomous Rover Traverse Required'}
            </p>
          </div>
        </div>
      </section>

      <section className="details__block">
        <p className="section-title">04 // SITE GEOMETRY</p>
        <div className="details__grid">
          <Stat
            label="LANDING ELLIPSE"
            value={
              mission.ellipseKm
                ? `${mission.ellipseKm[0] * 2}km × ${mission.ellipseKm[1] * 2}km`
                : '5km × 3km'
            }
          />
          <Stat
            label="TERRAIN SLOPE"
            value={
              typeof mission.slopeDeg === 'number'
                ? `${mission.slopeDeg.toFixed(1)}° (nominal)`
                : '5.0° (nominal)'
            }
          />
          <Stat
            label="ELEVATION"
            value={
              typeof mission.elevationM === 'number'
                ? `${mission.elevationM >= 0 ? '+' : '−'}${Math.abs(mission.elevationM).toLocaleString('en-US')}m`
                : 'NOMINAL'
            }
          />
          <Stat label="LAT / LON" value={formatCoords(mission.lat, mission.lon)} />
        </div>
      </section>

      <section className="details__block">
        <p className="section-title">05 // PAYLOAD MANIFEST (CLPS)</p>
        <div className="details__payloads">
          {(mission.payloads || []).map((p) => (
            <div className="payload" key={p.name}>
              <div className="payload__top">
                <strong>{p.name}</strong>
                <span className={`tag tag--${p.category || 'other'}`}>
                  {categoryLabel[p.category] || 'PAYLOAD'}
                </span>
              </div>
              <span>{p.detail}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="details__block details__block--provenance">
        <p className="section-title">06 // SCIENTIFIC PROVENANCE (NASA PDS)</p>
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
