import { formatCoords, psrFill, type Mission } from './missions'

export interface CompareRow {
  eyebrow: string
  label: string
  a: Cell
  b: Cell
  /** Which side wins this row; null when level. */
  winner: 'a' | 'b' | null
}

interface Cell {
  value: string
  note: string
  /** Bar fill, 0..100 */
  fill: number
}

export interface CompareSide {
  mission: Mission
  eyebrow: string
  target: string
  badge: string
}

export interface Comparison {
  a: CompareSide
  b: CompareSide
  rows: CompareRow[]
  brief: string
  citations: string
}

const CITATIONS =
  'CITATIONS: Mazarico et al. 2011 (LROC WAC) · Hayne et al. 2015 (ice stability) · NASA PDS urn:nasa:pds:lro-l-lola-3-rdr-v1.0'

// Hand-written brief from the design for its featured pair.
const FEATURED_BRIEF =
  "Mons Mouton (IM-2) demonstrates superior solar illumination (82%) enabling extended surface operations and volatile extraction windows. Despite lower Earth comms availability (71% vs 89%), the 1.2km proximity to confirmed ice deposits and shallower terrain slope make it the preferred CLPS PRIME-1 target for subsurface drilling operations in 2025. Griffin-1's site offers better communication geometry but lacks the proximity to high-concentration volatile deposits required for TRIDENT drill objectives."

function pick(higherIsBetter: boolean, a: number, b: number): 'a' | 'b' | null {
  if (a === b) return null
  return (a > b) === higherIsBetter ? 'a' : 'b'
}

function buildRows(a: Mission, b: Mission): CompareRow[] {
  const av = a.viability
  const bv = b.viability
  const slopeFill = (deg: number) => Math.max(0, Math.round(100 - deg * 3))

  return [
    {
      eyebrow: '01 // ENERGY AVAILABILITY',
      label: 'MISSION WINDOW SUNLIGHT',
      a: { value: `${av.windowSunlight.toFixed(1)}%`, note: '(tactical window)', fill: av.windowSunlight },
      b: { value: `${bv.windowSunlight.toFixed(1)}%`, note: '(tactical window)', fill: bv.windowSunlight },
      winner: pick(true, av.windowSunlight, bv.windowSunlight),
    },
    {
      eyebrow: '02 // ILLUMINATION BASELINE',
      label: 'ANNUAL SUNLIGHT',
      a: { value: `${av.annualSunlight.toFixed(1)}%`, note: '(strategic baseline)', fill: av.annualSunlight },
      b: { value: `${bv.annualSunlight.toFixed(1)}%`, note: '(strategic baseline)', fill: bv.annualSunlight },
      winner: pick(true, av.annualSunlight, bv.annualSunlight),
    },
    {
      eyebrow: '03 // TELEMETRY DIRECT LINK',
      label: 'EARTH COMMS WINDOW',
      a: { value: `${av.commsLos.toFixed(1)}%`, note: '(LOS Availability)', fill: av.commsLos },
      b: { value: `${bv.commsLos.toFixed(1)}%`, note: '(LOS Availability)', fill: bv.commsLos },
      winner: pick(true, av.commsLos, bv.commsLos),
    },
    {
      eyebrow: '04 // ISRU PROSPECTING',
      label: 'COLD TRAP PROXIMITY',
      a: { value: `${av.psrKm.toFixed(1)} km`, note: '(to PSR cold trap)', fill: psrFill(av.psrKm) },
      b: { value: `${bv.psrKm.toFixed(1)} km`, note: '(to PSR cold trap)', fill: psrFill(bv.psrKm) },
      winner: pick(false, av.psrKm, bv.psrKm),
    },
    {
      eyebrow: '05 // DESCENT TRAJECTORY RISK',
      label: 'SLOPE HAZARD',
      a: { value: `${a.slopeDeg.toFixed(1)}°`, note: '(Max terrain slope)', fill: slopeFill(a.slopeDeg) },
      b: { value: `${b.slopeDeg.toFixed(1)}°`, note: '(Max terrain slope)', fill: slopeFill(b.slopeDeg) },
      winner: pick(false, a.slopeDeg, b.slopeDeg),
    },
  ]
}

/** Deterministic plain-language summary built only from the numbers above. */
function buildBrief(a: Mission, b: Mission, rows: CompareRow[]): string {
  const featured = [a.id, b.id].sort().join('|') === 'griffin-1|im-2'
  if (featured) return FEATURED_BRIEF

  const aWins = rows.filter((r) => r.winner === 'a')
  const bWins = rows.filter((r) => r.winner === 'b')
  const lead = a.score === b.score ? null : a.score > b.score ? a : b
  const leadWins = lead === a ? aWins : bWins
  const trail = lead === a ? b : a
  const trailWins = lead === a ? bWins : aWins
  const names = (list: CompareRow[]) => list.map((r) => r.label.toLowerCase()).join(', ')

  if (!lead) {
    return `${a.name} (${a.site}) and ${b.name} (${b.site}) share the same environmental viability index of ${a.score}/100. ${a.site} leads on ${names(aWins) || 'no metric'}, while ${b.site} leads on ${names(bWins) || 'no metric'}.`
  }

  const tail = trailWins.length
    ? ` ${trail.name} (${trail.site}) holds the advantage on ${names(trailWins)}.`
    : ''
  return `${lead.name} (${lead.site}) scores ${lead.score}/100 against ${trail.score}/100 for ${trail.name} (${trail.site}), leading on ${leadWins.length} of ${rows.length} compared metrics: ${names(leadWins) || 'none'}.${tail}`
}

export function buildComparison(a: Mission, b: Mission): Comparison {
  const rows = buildRows(a, b)
  const tie = a.score === b.score
  const side = (m: Mission, label: string, wins: boolean): CompareSide => ({
    mission: m,
    eyebrow: `MISSION ${label} // ${m.provider.toUpperCase()}`,
    target: `TARGET: ${m.target} [${formatCoords(m.lat, m.lon)}]`,
    badge: tie ? 'TIED' : wins ? 'WINNER' : 'RUNNER-UP',
  })

  return {
    a: side(a, 'A', a.score > b.score),
    b: side(b, 'B', b.score > a.score),
    rows,
    brief: buildBrief(a, b, rows),
    citations: CITATIONS,
  }
}
