import { formatCoords, isLocated, type Mission } from './missions'
import type { TrackLookup } from './tracks'

export interface CompareRow {
  eyebrow: string
  label: string
  a: Cell
  b: Cell
  /** Which side wins this row; null when level or not comparable. */
  winner: 'a' | 'b' | null
}

interface Cell {
  value: string
  note: string
  /** Bar fill 0..100, or null when the value is unavailable. */
  fill: number | null
}

export interface CompareSide {
  mission: Mission
  eyebrow: string
  target: string
  badge: string
  /** Why track metrics are missing, if they are. */
  trackNote: string | null
}

export interface Comparison {
  a: CompareSide
  b: CompareSide
  rows: CompareRow[]
  brief: string
  citations: string
}

const CITATIONS =
  'DERIVED OUTPUT · NASA/JPL NAIF SPICE ephemeris · NASA LRO LOLA terrain · HUMAN SCIENTIFIC REVIEW PENDING'

interface Metrics {
  windowSunlight: number | null
  earthLos: number | null
  diskVisible: number | null
  psrKm: number | null
}

function metricsOf(t: TrackLookup): Metrics {
  if (t.state !== 'ready') return { windowSunlight: null, earthLos: null, diskVisible: null, psrKm: null }
  const { track, psr } = t.data
  return {
    windowSunlight: track.sunlit_percent,
    earthLos: track.earth_los_percent,
    diskVisible: track.mean_sun_disk_visible_fraction === null ? null : track.mean_sun_disk_visible_fraction * 100,
    psrKm: psr?.distance_km ?? null,
  }
}

function pick(higherIsBetter: boolean, a: number | null, b: number | null): 'a' | 'b' | null {
  if (a === null || b === null || a === b) return null
  return (a > b) === higherIsBetter ? 'a' : 'b'
}

const pct = (v: number | null): Cell['value'] => (v === null ? 'Unavailable' : `${v.toFixed(1)}%`)
const km = (v: number | null): Cell['value'] => (v === null ? 'Unavailable' : `${v.toFixed(2)} km`)
const clamp = (v: number | null) => (v === null ? null : Math.max(0, Math.min(100, v)))
/** Bar scale for distance: 0 km = full bar, 10 km or more = empty (display scale only). */
const distFill = (v: number | null) => (v === null ? null : clamp(100 - (v / 10) * 100))

function buildRows(a: Metrics, b: Metrics): CompareRow[] {
  return [
    {
      eyebrow: '01 // ENERGY AVAILABILITY',
      label: 'WINDOW SUNLIGHT',
      a: { value: pct(a.windowSunlight), note: '(29.5-day window, terrain-aware)', fill: clamp(a.windowSunlight) },
      b: { value: pct(b.windowSunlight), note: '(29.5-day window, terrain-aware)', fill: clamp(b.windowSunlight) },
      winner: pick(true, a.windowSunlight, b.windowSunlight),
    },
    {
      eyebrow: '02 // SOLAR DISC',
      label: 'MEAN SUN DISC VISIBLE',
      a: { value: pct(a.diskVisible), note: '(solar-power proxy)', fill: clamp(a.diskVisible) },
      b: { value: pct(b.diskVisible), note: '(solar-power proxy)', fill: clamp(b.diskVisible) },
      winner: pick(true, a.diskVisible, b.diskVisible),
    },
    {
      eyebrow: '03 // TELEMETRY DIRECT LINK',
      label: 'EARTH COMMS WINDOW',
      a: { value: pct(a.earthLos), note: '(direct line of sight)', fill: clamp(a.earthLos) },
      b: { value: pct(b.earthLos), note: '(direct line of sight)', fill: clamp(b.earthLos) },
      winner: pick(true, a.earthLos, b.earthLos),
    },
    {
      eyebrow: '04 // ISRU PROSPECTING',
      label: 'COLD TRAP PROXIMITY',
      a: { value: km(a.psrKm), note: '(to nearest PSR)', fill: distFill(a.psrKm) },
      b: { value: km(b.psrKm), note: '(to nearest PSR)', fill: distFill(b.psrKm) },
      winner: pick(false, a.psrKm, b.psrKm),
    },
  ]
}

/** Deterministic summary built only from the rows above; says so when data is missing. */
function buildBrief(a: Mission, b: Mission, rows: CompareRow[], aOk: boolean, bOk: boolean): string {
  if (!aOk || !bOk) {
    const missing = [!aOk && a.name, !bOk && b.name].filter(Boolean).join(' and ')
    return `No side-by-side metrics: ${missing} has no precomputed track, so illumination and Earth-link figures are unavailable. Nothing has been estimated in their place.`
  }
  const names = (list: CompareRow[]) => list.map((r) => r.label.toLowerCase()).join(', ')
  const aWins = rows.filter((r) => r.winner === 'a')
  const bWins = rows.filter((r) => r.winner === 'b')
  const aLead = aWins.length ? `${a.name} leads on ${names(aWins)}.` : `${a.name} leads on no metric.`
  const bLead = bWins.length ? `${b.name} leads on ${names(bWins)}.` : `${b.name} leads on no metric.`
  return `${aLead} ${bLead} Figures are computed over each mission's own 29.5-day window, so they describe that window only, not an annual baseline.`
}

export function buildComparison(a: Mission, b: Mission, ta: TrackLookup, tb: TrackLookup): Comparison {
  const rows = buildRows(metricsOf(ta), metricsOf(tb))
  const aWins = rows.filter((r) => r.winner === 'a').length
  const bWins = rows.filter((r) => r.winner === 'b').length
  const noteOf = (t: TrackLookup) =>
    t.state === 'none' || t.state === 'error' ? t.reason : t.state === 'loading' ? 'Loading track…' : null
  const side = (m: Mission, label: string, wins: number, other: number, t: TrackLookup): CompareSide => ({
    mission: m,
    eyebrow: `MISSION ${label} // ${m.provider.toUpperCase()}`,
    target: isLocated(m)
      ? `TARGET: ${m.targetSite} [${formatCoords(m.lat, m.lon)}]`
      : `TARGET: ${m.targetSite} [NO COORDINATE PUBLISHED]`,
    badge: t.state !== 'ready' ? 'NO TRACK' : wins === other ? 'LEVEL' : wins > other ? 'LEADS' : 'TRAILS',
    trackNote: noteOf(t),
  })

  return {
    a: side(a, 'A', aWins, bWins, ta),
    b: side(b, 'B', bWins, aWins, tb),
    rows,
    brief: buildBrief(a, b, rows, ta.state === 'ready', tb.state === 'ready'),
    citations: CITATIONS,
  }
}
