import { useEffect, useMemo, useState } from 'react'
import { buildComparison, type CompareRow, type CompareSide } from '../data/compare'
import { getMission, missions, type Mission } from '../data/missions'
import {
  compareLaunchDates,
  fetchSiteScore,
  type LaunchSlipComparison,
  type SiteScoreResponse,
} from '../services/api'
import './CompareView.css'

interface CompareViewProps {
  aId: string
  bId: string
  onChange: (aId: string, bId: string) => void
  onBack: () => void
  missionsList?: Mission[]
}

export function CompareView({
  aId,
  bId,
  onChange,
  onBack,
  missionsList = missions,
}: CompareViewProps) {
  const [compareMode, setCompareMode] = useState<'sites' | 'dates'>('sites')

  // Date A vs Date B launch slip state
  const [dateA, setDateA] = useState('2026-11-15T12:00:00Z')
  const [dateB, setDateB] = useState('2026-11-18T12:00:00Z')
  const [slipData, setSlipData] = useState<LaunchSlipComparison | null>(null)
  const [slipLoading, setSlipLoading] = useState(false)

  const rawA = useMemo(() => getMission(aId, missionsList), [aId, missionsList])
  const rawB = useMemo(() => getMission(bId, missionsList), [bId, missionsList])

  const [scoreA, setScoreA] = useState<SiteScoreResponse | null>(null)
  const [scoreB, setScoreB] = useState<SiteScoreResponse | null>(null)

  useEffect(() => {
    let active = true
    fetchSiteScore(rawA.lat, rawA.lon, rawA.start_date, rawA.end_date).then((res) => {
      if (active) setScoreA(res)
    })
    fetchSiteScore(rawB.lat, rawB.lon, rawB.start_date, rawB.end_date).then((res) => {
      if (active) setScoreB(res)
    })
    return () => {
      active = false
    }
  }, [rawA.lat, rawA.lon, rawA.start_date, rawA.end_date, rawB.lat, rawB.lon, rawB.start_date, rawB.end_date])

  // Fetch Launch Slip evaluation when comparing dates
  useEffect(() => {
    if (compareMode !== 'dates') return
    let active = true
    setSlipLoading(true)
    compareLaunchDates(aId, dateA, dateB).then((res) => {
      if (active) {
        setSlipData(res)
        setSlipLoading(false)
      }
    })
    return () => {
      active = false
    }
  }, [compareMode, aId, dateA, dateB])

  const applySlipOffsetHours = (hours: number) => {
    try {
      const base = new Date(dateA)
      base.setHours(base.getHours() + hours)
      setDateB(base.toISOString().replace('.000Z', 'Z'))
    } catch {}
  }

  const missionA = useMemo(() => {
    if (!scoreA) return rawA
    return {
      ...rawA,
      score: Math.round(scoreA.viability_score),
      viability: {
        windowSunlight: scoreA.tactical_mission_sunlight_percent,
        annualSunlight: scoreA.strategic_annual_baseline_percent,
        commsLos: scoreA.comms_uptime_percent,
        psrKm: scoreA.psr_distance_km,
      },
    }
  }, [rawA, scoreA])

  const missionB = useMemo(() => {
    if (!scoreB) return rawB
    return {
      ...rawB,
      score: Math.round(scoreB.viability_score),
      viability: {
        windowSunlight: scoreB.tactical_mission_sunlight_percent,
        annualSunlight: scoreB.strategic_annual_baseline_percent,
        commsLos: scoreB.comms_uptime_percent,
        psrKm: scoreB.psr_distance_km,
      },
    }
  }, [rawB, scoreB])

  const comparison = useMemo(
    () => buildComparison(missionA, missionB),
    [missionA, missionB]
  )
  const { a, b, rows, brief, citations } = comparison

  return (
    <div className="compare">
      <div className="compare__inner">
        <div className="compare__bar">
          <button type="button" className="compare__back" onClick={onBack}>
            ◀ BACK TO FLEET
          </button>

          {/* Mode switch: Compare Two Sites vs Launch Slip Date A vs Date B */}
          <div className="compare__mode-tabs">
            <button
              type="button"
              className={`compare__mode-tab ${compareMode === 'sites' ? 'compare__mode-tab--active' : ''}`}
              onClick={() => setCompareMode('sites')}
            >
              ⇄ COMPARE TWO SITES
            </button>
            <button
              type="button"
              className={`compare__mode-tab ${compareMode === 'dates' ? 'compare__mode-tab--active' : ''}`}
              onClick={() => setCompareMode('dates')}
            >
              ⏱ LAUNCH SLIP (DATE A VS B)
            </button>
          </div>

          {compareMode === 'sites' ? (
            <div className="compare__pickers">
              <Picker
                label="SITE A"
                value={aId}
                other={bId}
                missionsList={missionsList}
                onChange={(id) => onChange(id, bId)}
              />
              <span className="compare__vs">VS</span>
              <Picker
                label="SITE B"
                value={bId}
                other={aId}
                missionsList={missionsList}
                onChange={(id) => onChange(aId, id)}
              />
            </div>
          ) : (
            <div className="compare__pickers">
              <Picker
                label="EVALUATE SITE"
                value={aId}
                other=""
                missionsList={missionsList}
                onChange={(id) => onChange(id, bId)}
              />
            </div>
          )}
        </div>

        {compareMode === 'dates' ? (
          /* LAUNCH SLIP ANALYSIS PANEL */
          <div className="launch-slip-panel">
            <div className="launch-slip__inputs">
              <div className="slip-input-group">
                <label>PLANNED LAUNCH (DATE A)</label>
                <input
                  type="text"
                  value={dateA}
                  onChange={(e) => setDateA(e.target.value)}
                  placeholder="YYYY-MM-DDTHH:MM:SSZ"
                />
              </div>
              <div className="slip-offsets">
                <span className="slip-offsets__label">QUICK SLIP:</span>
                <button type="button" onClick={() => applySlipOffsetHours(24)}>+24h</button>
                <button type="button" onClick={() => applySlipOffsetHours(48)}>+48h</button>
                <button type="button" onClick={() => applySlipOffsetHours(72)}>+72h</button>
                <button type="button" onClick={() => applySlipOffsetHours(168)}>+7 days</button>
              </div>
              <div className="slip-input-group">
                <label>SLIPPED ARRIVAL (DATE B)</label>
                <input
                  type="text"
                  value={dateB}
                  onChange={(e) => setDateB(e.target.value)}
                  placeholder="YYYY-MM-DDTHH:MM:SSZ"
                />
              </div>
            </div>

            {slipLoading ? (
              <div className="slip-loading">Evaluating synchronized SPICE ephemeris tracks...</div>
            ) : slipData ? (
              <div className="slip-results">
                <div className="slip-cards">
                  <div className="slip-card">
                    <header className="slip-card__head">
                      <span>SCENARIO A (PLANNED)</span>
                      <strong>{slipData.date_a.start_utc.slice(0, 10)}</strong>
                    </header>
                    <div className="slip-card__body">
                      <div className="slip-stat">
                        <span>14-DAY SUNLIGHT</span>
                        <strong>{slipData.date_a.sunlit_percent.toFixed(1)}%</strong>
                      </div>
                      <div className="slip-stat">
                        <span>EARTH LOS</span>
                        <strong>{slipData.date_a.earth_los_percent.toFixed(1)}%</strong>
                      </div>
                      <div className="slip-stat">
                        <span>ARRIVAL LIGHT</span>
                        <strong className={slipData.date_a.sun.is_lit ? 'tag--ok' : 'tag--warn'}>
                          {slipData.date_a.sun.is_lit ? '☀️ SUNLIT' : '🌑 SHADOW'}
                        </strong>
                      </div>
                    </div>
                  </div>

                  <div className="slip-card slip-card--delta">
                    <header className="slip-card__head">
                      <span>DELTA (B − A)</span>
                      <strong>{slipData.delta_b_minus_a.lit_at_arrival_changed ? '⚠ LIGHTING FLIPPED' : '✓ STABLE'}</strong>
                    </header>
                    <div className="slip-card__body">
                      <div className="slip-stat">
                        <span>SUNLIGHT IMPACT</span>
                        <strong className={Number(slipData.delta_b_minus_a.sunlit_percent) >= 0 ? 'tag--ok' : 'tag--warn'}>
                          {Number(slipData.delta_b_minus_a.sunlit_percent) >= 0 ? `+${slipData.delta_b_minus_a.sunlit_percent}%` : `${slipData.delta_b_minus_a.sunlit_percent}%`}
                        </strong>
                      </div>
                      <div className="slip-stat">
                        <span>EARTH LOS IMPACT</span>
                        <strong>
                          {Number(slipData.delta_b_minus_a.earth_los_percent) >= 0 ? `+${slipData.delta_b_minus_a.earth_los_percent}%` : `${slipData.delta_b_minus_a.earth_los_percent}%`}
                        </strong>
                      </div>
                      <p className="slip-delta-desc">
                        {slipData.delta_b_minus_a.lit_at_arrival_changed
                          ? 'CRITICAL ALERT: Launch slip pushes touchdown into shadow! Thermal survival battery required.'
                          : 'Nominal launch slip: Illumination regime remains stable within operational envelope.'}
                      </p>
                    </div>
                  </div>

                  <div className="slip-card">
                    <header className="slip-card__head">
                      <span>SCENARIO B (SLIPPED)</span>
                      <strong>{slipData.date_b.start_utc.slice(0, 10)}</strong>
                    </header>
                    <div className="slip-card__body">
                      <div className="slip-stat">
                        <span>14-DAY SUNLIGHT</span>
                        <strong>{slipData.date_b.sunlit_percent.toFixed(1)}%</strong>
                      </div>
                      <div className="slip-stat">
                        <span>EARTH LOS</span>
                        <strong>{slipData.date_b.earth_los_percent.toFixed(1)}%</strong>
                      </div>
                      <div className="slip-stat">
                        <span>ARRIVAL LIGHT</span>
                        <strong className={slipData.date_b.sun.is_lit ? 'tag--ok' : 'tag--warn'}>
                          {slipData.date_b.sun.is_lit ? '☀️ SUNLIT' : '🌑 SHADOW'}
                        </strong>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="slip-provenance">
                  <span>HORIZON MODEL: <strong>{slipData.horizon_model}</strong></span>
                  <span>EVALUATION: <strong>Synchronized 14-day SPICE tracks · Shared relative clock</strong></span>
                </div>
              </div>
            ) : null}
          </div>
        ) : (
          /* STANDARD TWO-SITE COMPARISON VIEW */
          <>
            <div className="compare__cards">
              <MissionCard side={a} winner={a.badge === 'WINNER'} />
              <MissionCard side={b} winner={b.badge === 'WINNER'} />
            </div>

            <div className="compare__matrix" role="table" aria-label="Comparison matrix">
              <div className="matrix__row matrix__row--head" role="row">
                <span className="matrix__metric">METRIC</span>
                <span className="matrix__cell matrix__cell--head matrix__cell--accent">
                  {a.mission.name.toUpperCase()} · {a.mission.site.toUpperCase()}
                </span>
                <span className="matrix__cell matrix__cell--head">
                  {b.mission.name.toUpperCase()} · {b.mission.site.toUpperCase()}
                </span>
              </div>
              {rows.map((row, i) => (
                <MatrixRow key={row.label} row={row} tinted={i % 2 === 0} />
              ))}
            </div>

            <section className="compare__brief">
              <header>
                <span className="compare__brief-dot" />
                <h3>06 // PLAIN-LANGUAGE SCIENCE BRIEF</h3>
              </header>
              <p>{brief}</p>
              <footer>
                <span>{citations}</span>
                <span>
                  SECURITY: UNCLASSIFIED // <em>NASA GSFC</em>
                </span>
              </footer>
            </section>
          </>
        )}
      </div>
    </div>
  )
}

function Picker({
  label,
  value,
  other,
  onChange,
  missionsList,
}: {
  label: string
  value: string
  other: string
  onChange: (id: string) => void
  missionsList: Mission[]
}) {
  return (
    <label className="picker">
      <span className="picker__label">{label}</span>
      <select
        className="picker__select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={label}
      >
        {missionsList.map((m) => (
          <option key={m.id} value={m.id} disabled={m.id === other}>
            {m.index ? `${m.index}. ` : ''}{m.name} — {m.site}
          </option>
        ))}
      </select>
    </label>
  )
}

function MissionCard({ side, winner }: { side: CompareSide; winner: boolean }) {
  const { mission, badge } = side
  return (
    <article className={`m-card${winner ? ' m-card--winner' : ''}`}>
      <div className="m-card__top">
        <span className="m-card__badge">{badge}</span>
        <span className="m-card__tag">
          {mission.provider} // {mission.lander}
        </span>
      </div>

      <h3 className="m-card__name">{mission.name}</h3>
      <p className="m-card__site">
        {mission.site} · {mission.year}
      </p>

      <div className="m-card__score">
        <span className="m-card__num">{mission.score}</span>
        <span className="m-card__max">/ 100</span>
        <span className="m-card__tag m-card__tag--right">TOTAL SCORE</span>
      </div>
    </article>
  )
}

function MatrixRow({ row, tinted }: { row: CompareRow; tinted: boolean }) {
  return (
    <div
      className={`matrix__row${tinted ? ' matrix__row--tint' : ''}`}
      role="row"
    >
      <span className="matrix__metric" role="rowheader">
        {row.label}
      </span>
      <Cell side={row.a} />
      <Cell side={row.b} />
    </div>
  )
}

function Cell({ side }: { side: CompareRow['a'] }) {
  const warn = side.note?.includes('FAILS') ? ' matrix__cell--warn' : ''
  return (
    <span className={`matrix__cell${warn}`} role="cell">
      <strong>{side.value}</strong>
      {side.note && <span className="matrix__sub">{side.note}</span>}
    </span>
  )
}
