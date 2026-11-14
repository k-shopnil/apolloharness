import { useEffect, useMemo, useState } from 'react'
import { fetchDateComparison, useEngineStatus, type DateComparison, type DateRun } from '../data/api'
import { formatCoords, isLocated, type Mission } from '../data/missions'
import { horizonLabel, loadTrackIndex } from '../data/tracks'
import { Icon } from './Icon'
import { PleaseWait } from './PleaseWait'
import './DateCompare.css'

interface Props {
  missions: Mission[]
  initialSiteId: string
}

const DURATIONS = [7, 14, 29.5]
const SLIPS: [string, number][] = [
  ['+24 h', 24],
  ['+72 h', 72],
  ['+7 days', 168],
]

const toInput = (utc: string) => utc.slice(0, 16)
const fromInput = (v: string) => `${v}:00Z`
const addHours = (input: string, h: number) => new Date(Date.parse(`${input}:00Z`) + h * 3_600_000).toISOString().slice(0, 16)
const showUtc = (utc: string) => `${utc.slice(0, 16).replace('T', ' ')} UTC`
const pct = (v: number | null) => (v === null ? 'Unavailable' : `${v.toFixed(1)}%`)
const pp = (v: number | null) => (v === null ? 'Unavailable' : `${v > 0 ? '+' : v < 0 ? '−' : '±'}${Math.abs(v).toFixed(1)} pts`)

type State = { state: 'idle' } | { state: 'loading' } | { state: 'ready'; data: DateComparison } | { state: 'error'; reason: string }

/** Same site, two start dates: how a launch slip changes sunlight and Earth contact (live engine). */
export function DateCompare({ missions, initialSiteId }: Props) {
  const engine = useEngineStatus()
  const sites = useMemo(() => missions.filter(isLocated), [missions])
  const [siteId, setSiteId] = useState(sites.some((m) => m.id === initialSiteId) ? initialSiteId : sites[0]?.id)
  const [dateA, setDateA] = useState('')
  const [dateB, setDateB] = useState('')
  const [duration, setDuration] = useState(14)
  const [result, setResult] = useState<State>({ state: 'idle' })
  const site = sites.find((m) => m.id === siteId)

  // Default Date A: the start of the mission's precomputed window (else its target date, else today); Date B: 72 h later.
  useEffect(() => {
    let cancelled = false
    const fallback = site?.targetDate && /^\d{4}-\d{2}-\d{2}$/.test(site.targetDate) ? `${site.targetDate}T00:00` : new Date().toISOString().slice(0, 10) + 'T00:00'
    loadTrackIndex()
      .then((index) => index.get(siteId ?? '')?.window_start_utc)
      .catch(() => undefined)
      .then((start) => {
        if (cancelled) return
        const a = start ? toInput(start) : fallback
        setDateA(a)
        setDateB(addHours(a, 72))
        setResult({ state: 'idle' })
      })
    return () => {
      cancelled = true
    }
  }, [siteId, site?.targetDate])

  const run = () => {
    if (!siteId || !dateA || !dateB) return
    setResult({ state: 'loading' })
    fetchDateComparison(siteId, fromInput(dateA), fromInput(dateB), duration)
      .then((data) => setResult({ state: 'ready', data }))
      .catch((e: Error) => setResult({ state: 'error', reason: e.message }))
  }

  const engineDown = engine === 'offline' || engine === 'disabled'

  return (
    <section className="dates">
      <p className="dates__lead">
        If a launch slips, does the site fall into shadow or lose sight of Earth? Pick a site and two start times. The live
        engine computes both windows from NASA SPICE and LOLA data.
      </p>

      <form
        className="dates__form"
        onSubmit={(e) => {
          e.preventDefault()
          run()
        }}
      >
        <label className="dates__field dates__field--site">
          <span>Site</span>
          <select value={siteId} onChange={(e) => setSiteId(e.target.value)}>
            {sites.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name} — {m.targetSite}
              </option>
            ))}
          </select>
        </label>
        <label className="dates__field">
          <span>Date A (UTC)</span>
          <input type="datetime-local" value={dateA} onChange={(e) => setDateA(e.target.value)} required />
        </label>
        <label className="dates__field">
          <span>Date B (UTC)</span>
          <input type="datetime-local" value={dateB} onChange={(e) => setDateB(e.target.value)} required />
        </label>
        <div className="dates__field">
          <span>Slip B from A</span>
          <div className="segmented">
            {SLIPS.map(([label, h]) => (
              <button key={label} type="button" aria-pressed={dateA !== '' && dateB === addHours(dateA, h)} onClick={() => dateA && setDateB(addHours(dateA, h))}>
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="dates__field">
          <span>Window</span>
          <div className="segmented">
            {DURATIONS.map((d) => (
              <button key={d} type="button" aria-pressed={duration === d} onClick={() => setDuration(d)}>
                {d} days
              </button>
            ))}
          </div>
        </div>
        <button type="submit" className="dates__go" disabled={result.state === 'loading' || !dateA || !dateB || engineDown}>
          {result.state === 'loading' ? 'Calculating…' : 'Compare dates'}
        </button>
      </form>

      {engineDown && (
        <p className="dates__note">
          The live engine is not reachable right now, so dates can't be compared. Mission tracks on the globe still work.
        </p>
      )}
      {result.state === 'loading' && <PleaseWait task={`Computing two ${duration}-day windows`} live />}
      {result.state === 'error' && <p className="dates__note dates__note--error">{result.reason}</p>}
      {result.state === 'ready' && site && <Result data={result.data} site={site} />}
    </section>
  )
}

function Result({ data, site }: { data: DateComparison; site: Mission }) {
  const d = data.delta_b_minus_a
  const summary =
    d.sunlit_percent === null
      ? 'Sunlight could not be computed for one of the windows.'
      : `Moving the start from A to B changes sunlight over the next ${data.duration_days} days by ${pp(d.sunlit_percent)}` +
        (d.earth_los_percent === null ? '.' : ` and time with Earth in view by ${pp(d.earth_los_percent)}.`) +
        (d.lit_at_arrival_changed === true
          ? ' The Sun is up at one start time and down at the other.'
          : d.lit_at_arrival_changed === false
            ? ' Whether the Sun is up at the start does not change.'
            : '')

  return (
    <div className="dates__result">
      <p className="dates__summary">{summary}</p>
      <div className="dates__cards">
        <RunCard label="Date A" run={data.date_a} days={data.duration_days} />
        <RunCard label="Date B" run={data.date_b} days={data.duration_days} />
      </div>
      <dl className="dates__delta">
        <div>
          <dt>Sunlight, B − A</dt>
          <dd>{pp(d.sunlit_percent)}</dd>
        </div>
        <div>
          <dt>Earth in view, B − A</dt>
          <dd>{pp(d.earth_los_percent)}</dd>
        </div>
        <div>
          <dt>Sun up at start changes</dt>
          <dd>{d.lit_at_arrival_changed === null ? 'Unavailable' : d.lit_at_arrival_changed ? 'Yes' : 'No'}</dd>
        </div>
      </dl>
      <p className="dates__note">
        {site.name} · {formatCoords(data.latitude_deg, data.longitude_deg)} · {horizonLabel(data.horizon_model)}
        {data.terrain?.dem_product ? ` · ${data.terrain.dem_product}` : ''}. Each window starts at its own date; figures
        describe those windows only.
      </p>
    </div>
  )
}

function RunCard({ label, run, days }: { label: string; run: DateRun; days: number }) {
  const cols = run.track?.columns
  return (
    <article className="dates__card">
      <p className="dates__card-label">
        <Icon name="calendar" size={14} />
        {label} · {showUtc(run.start_utc)}
      </p>
      <div className="dates__figures">
        <div>
          <span>Sunlight</span>
          <strong>{pct(run.sunlit_percent)}</strong>
        </div>
        <div>
          <span>Earth in view</span>
          <strong>{pct(run.earth_los_percent)}</strong>
        </div>
      </div>
      <p className="dates__start">
        <span data-tone={run.sun.is_lit === null ? 'warn' : run.sun.is_lit ? 'ok' : 'bad'}>
          <Icon name="sun" size={14} />
          {run.sun.is_lit === null ? 'Sun: unknown' : run.sun.is_lit ? 'Sun up at start' : 'Sun down at start'}
        </span>
        <span data-tone={run.earth.direct_los === null ? 'warn' : run.earth.direct_los ? 'ok' : 'bad'}>
          <Icon name="earth" size={14} />
          {run.earth.direct_los === null ? 'Earth: unknown' : run.earth.direct_los ? 'Earth in view' : 'Earth hidden'}
        </span>
      </p>
      {cols && (
        <div className="dates__strips" aria-label={`${label}: sunlight and Earth view over ${days} days`}>
          <Strip label="Sun" flags={cols.sun_lit} />
          <Strip label="Earth" flags={cols.earth_los} />
          <div className="dates__axis">
            <span>start</span>
            <span>+{days} days</span>
          </div>
        </div>
      )}
    </article>
  )
}

function Strip({ label, flags }: { label: string; flags: (boolean | null)[] }) {
  const runs = useMemo(() => {
    const out: { start: number; len: number; v: boolean | null }[] = []
    flags.forEach((v, i) => {
      const last = out[out.length - 1]
      if (last && last.v === v) last.len++
      else out.push({ start: i, len: 1, v })
    })
    return out
  }, [flags])
  return (
    <div className="scrub__strip">
      <span className="scrub__strip-label">
        <Icon name={label === 'Sun' ? 'sun' : 'earth'} size={13} />
        {label}
      </span>
      <div className="scrub__strip-bar">
        {runs.map((r) => (
          <i
            key={r.start}
            data-state={r.v === null ? 'unknown' : r.v ? 'on' : 'off'}
            style={{ left: `${(r.start / flags.length) * 100}%`, width: `${(r.len / flags.length) * 100}%` }}
          />
        ))}
      </div>
    </div>
  )
}
