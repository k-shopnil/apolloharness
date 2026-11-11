/**
 * Mission catalog, loaded from the engine's data/missions.json (copied to
 * public/data by scripts/copy-data.mjs). Nothing in here is hand-written
 * science: every value comes from the catalog, and unknowns stay null.
 */

export type MissionFilter = 'all' | 'volatiles' | 'spectrometers' | 'rovers'
export type PayloadCategory = 'volatiles' | 'spectrometers' | 'rovers' | 'other'
export type MissionKind = 'clps' | 'reference_anchor'

export interface Payload {
  name: string
  /** Raw purpose tags from the catalog, e.g. "water_ice". */
  purpose: string[]
  category: PayloadCategory
}

export interface Source {
  publisher: string
  title: string
  url: string
}

export interface Mission {
  /** Canonical id from data/missions.json, e.g. "clps-prime-1-im2". */
  id: string
  /** Mission name, e.g. "IM-2 Athena". */
  name: string
  kind: MissionKind
  provider: string
  lander: string
  taskOrder: string
  targetSite: string
  region: string
  status: string
  statusNote: string | null
  /** ISO date or year string as published; null when TBD. */
  targetDate: string | null
  touchdownUtc: string | null
  /** Reference anchors only: the lesson this landing provides, as published in the catalog. */
  baselineRole: { tag: string; text: string } | null
  /** Selenographic degrees (south/west negative). null = no coordinate published. */
  lat: number | null
  lon: number | null
  coordinateType: string
  coordinateProvenance: string
  /** Only an actual_landing coordinate may be presented as a landing fix. */
  isLandingFix: boolean
  /** Landing ellipse axes in km; null = unpublished (never invent one). */
  ellipseMajorKm: number | null
  ellipseMinorKm: number | null
  payloadSummary: string
  payloads: Payload[]
  sources: Source[]
}

/** A mission that has a coordinate and can be drawn on the globe. */
export type LocatedMission = Mission & { lat: number; lon: number }

export function isLocated(m: Mission): m is LocatedMission {
  return m.lat !== null && m.lon !== null
}

interface RawMission {
  id: string
  mission: string
  category: string
  provider: string
  lander: string
  task_order: string
  target_site: string
  region: string
  status: string
  status_note?: string
  target_date: string | null
  touchdown_utc?: string
  baseline_role?: string
  landing_site: {
    latitude_deg: number | null
    longitude_deg: number | null
    coordinate_type: string
    coordinate_provenance: string
  }
  landing_ellipse_km?: { major_axis_km: number | null; minor_axis_km: number | null }
  payload_summary: string
  payloads: { name: string; purpose: string[] }[]
  sources: { publisher: string; title: string; url: string }[]
}

/** Payload category from the catalog's purpose tags (first match wins). */
export function categorize(purpose: string[]): PayloadCategory {
  const tags = purpose.join(' ')
  if (/rover/.test(tags)) return 'rovers'
  if (/spectromet|spectral/.test(tags)) return 'spectrometers'
  if (/volatile|water|ice|drill|prospect|resource|subsurface/.test(tags)) return 'volatiles'
  return 'other'
}

/** Catalog format is "tag: sentence". */
function parseBaseline(raw: string | undefined): Mission['baselineRole'] {
  if (!raw) return null
  const i = raw.indexOf(':')
  return i < 0 ? { tag: 'baseline', text: raw } : { tag: raw.slice(0, i).trim(), text: raw.slice(i + 1).trim() }
}

function normalize(raw: RawMission): Mission {
  const site = raw.landing_site
  return {
    id: raw.id,
    name: raw.mission,
    kind: raw.category === 'reference_anchor' ? 'reference_anchor' : 'clps',
    provider: raw.provider,
    lander: raw.lander,
    taskOrder: raw.task_order,
    targetSite: raw.target_site,
    region: raw.region,
    status: raw.status,
    statusNote: raw.status_note ?? null,
    targetDate: raw.target_date ?? null,
    touchdownUtc: raw.touchdown_utc ?? null,
    baselineRole: parseBaseline(raw.baseline_role),
    lat: site.latitude_deg,
    lon: site.longitude_deg,
    coordinateType: site.coordinate_type,
    coordinateProvenance: site.coordinate_provenance,
    isLandingFix: site.coordinate_type === 'actual_landing',
    ellipseMajorKm: raw.landing_ellipse_km?.major_axis_km ?? null,
    ellipseMinorKm: raw.landing_ellipse_km?.minor_axis_km ?? null,
    payloadSummary: raw.payload_summary,
    payloads: raw.payloads.map((p) => ({ name: p.name, purpose: p.purpose, category: categorize(p.purpose) })),
    sources: raw.sources.map(({ publisher, title, url }) => ({ publisher, title, url })),
  }
}

export const DATA_BASE = `${import.meta.env.BASE_URL}data/`

/** Loads the catalog. Terminated missions (e.g. Draper CP-12) are hidden. */
export async function loadMissions(): Promise<Mission[]> {
  const res = await fetch(`${DATA_BASE}missions.json`)
  if (!res.ok) throw new Error(`missions.json: HTTP ${res.status}`)
  const raw = (await res.json()) as RawMission[]
  return raw.filter((m) => m.status !== 'terminated').map(normalize)
}

export type MissionGroup = 'all' | 'fleet' | 'anchors'

export const groupTabs: { id: MissionGroup; label: string }[] = [
  { id: 'all', label: 'ALL' },
  { id: 'fleet', label: 'FLEET' },
  { id: 'anchors', label: 'ANCHORS' },
]

/** Fleet = CLPS missions; anchors = past real landings used as yardsticks. */
export function inGroup(mission: Mission, group: MissionGroup): boolean {
  return group === 'all' || (group === 'anchors') === (mission.kind === 'reference_anchor')
}

export const filterTabs: { id: MissionFilter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'volatiles', label: '★ Volatiles & Drills' },
  { id: 'spectrometers', label: 'Spectrometers' },
  { id: 'rovers', label: 'Rovers & Mobility' },
]

export const categoryLabel: Record<PayloadCategory, string> = {
  volatiles: 'VOLATILES & DRILLS',
  spectrometers: 'SPECTROMETERS',
  rovers: 'ROVERS',
  other: 'INSTRUMENT',
}

export function matchesFilter(mission: Mission, filter: MissionFilter): boolean {
  return filter === 'all' || mission.payloads.some((p) => p.category === filter)
}

export function missionsFor(missions: Mission[], filter: MissionFilter): Mission[] {
  return missions.filter((m) => matchesFilter(m, filter))
}

/** "actual_landing" -> "ACTUAL LANDING". */
export function humanize(tag: string): string {
  return tag.replace(/_/g, ' ').toUpperCase()
}

/** Short badge text for how far a coordinate can be trusted. */
export function coordinateBadge(m: Mission): string {
  if (m.lat === null || m.lon === null) return 'NO COORDINATE PUBLISHED'
  if (m.isLandingFix) return 'ACTUAL LANDING'
  if (m.coordinateType === 'reported_landing_rounded') return 'REPORTED LANDING (ROUNDED)'
  return 'TARGET / REFERENCE'
}

export function missionYear(m: Mission): string {
  return m.targetDate ? m.targetDate.slice(0, 4) : 'TBD'
}

export function formatCoords(lat: number, lon: number): string {
  const ns = lat < 0 ? 'S' : 'N'
  const e = ((lon % 360) + 360) % 360
  return `${Math.abs(lat).toFixed(2)}°${ns}, ${e.toFixed(2)}°E`
}
