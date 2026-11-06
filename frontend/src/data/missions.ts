export type MissionFilter = 'all' | 'volatiles' | 'spectrometers' | 'rovers'
export type PayloadCategory = 'volatiles' | 'spectrometers' | 'rovers' | 'other'

export interface Payload {
  name: string
  detail: string
  category: PayloadCategory
}

/** Raw inputs behind the Environmental Viability Index bars. */
export interface Viability {
  /** Sunlit share of the tactical mission window, %. */
  windowSunlight: number
  /** Strategic annual sunlight baseline, %. */
  annualSunlight: number
  /** Earth line-of-sight availability, %. */
  commsLos: number
  /** Distance to the nearest permanently shadowed (PSR) cold trap, km. */
  psrKm: number
}

export interface Mission {
  id: string
  index: string
  name: string
  provider: string
  lander: string
  launchWindow: string
  site: string
  /** Longer geographic description shown in the drawer. */
  target: string
  year: number
  /** Selenographic latitude in degrees (south negative). */
  lat: number
  /** Selenographic longitude in degrees east, -180..180. */
  lon: number
  start_date?: string
  end_date?: string
  /** Landing ellipse semi-axes in km (major, minor). */
  ellipseKm: [number, number]
  slopeDeg: number
  elevationM: number
  score: number
  viability: Viability
  /** Short instrument list for sidebar cards. */
  payloadSummary: string
  payloads: Payload[]
  /**
   * 'figma' values come from the design file. 'placeholder' values are illustrative
   * until the real PDS-derived numbers are wired in, and the UI labels them as such.
   */
  dataStatus: 'figma' | 'placeholder'
  /** Cards used by the filtered sidebars in the design. */
  filtered?: {
    volatiles?: FilteredCard
    rovers?: FilteredCard
  }
}

interface FilteredCard {
  title: string
  badge: string
  site: string
  payload: string
  viability?: { value: string; tag: string; accent?: boolean }
}

export const missions: Mission[] = [
  {
    id: 'im-1',
    payloadSummary: 'ROLSES, LN-1, NDL',
    index: '01',
    name: 'Nova-C Odysseus',
    provider: 'Intuitive Machines',
    lander: 'Nova-C (IM-1)',
    launchWindow: 'Feb 2024',
    site: 'Malapert A',
    target: 'Malapert A, near the south pole',
    year: 2024,
    lat: -86.0,
    lon: 4.0,
    ellipseKm: [4, 2.5],
    slopeDeg: 6.1,
    elevationM: 1480,
    score: 61,
    viability: { windowSunlight: 58, annualSunlight: 49, commsLos: 77, psrKm: 6.8 },
    payloads: [
      { name: 'ROLSES', detail: 'NASA GSFC · Radio observations of the lunar surface environment', category: 'other' },
      { name: 'LN-1', detail: 'NASA MSFC · Autonomous navigation demonstration', category: 'other' },
      { name: 'NDL', detail: 'NASA LaRC · Navigation Doppler Lidar for precision landing', category: 'other' },
    ],
    dataStatus: 'placeholder',
  },
  {
    id: 'im-2',
    payloadSummary: 'TRIDENT, MSolo, PRIME-1',
    index: '02',
    name: 'Nova-C Athena',
    provider: 'Intuitive Machines',
    lander: 'Nova-C (IM-2)',
    launchWindow: 'Feb 2025',
    site: 'Mons Mouton',
    target: 'Mons Mouton Plateau, Shackleton–de Gerlache ridge',
    year: 2025,
    lat: -84.8,
    lon: 29.2,
    ellipseKm: [2.5, 1.5],
    slopeDeg: 4.8,
    elevationM: 1920,
    score: 79,
    viability: { windowSunlight: 82, annualSunlight: 68, commsLos: 71, psrKm: 1.2 },
    payloads: [
      { name: 'TRIDENT 1M SUBSURFACE DRILL', detail: 'NASA KSC · Target: 1-meter regolith ice extraction', category: 'volatiles' },
      { name: 'MSolo MASS SPECTROMETER', detail: 'NASA Ames · Target: Real-time volatile desorption', category: 'spectrometers' },
      { name: 'PRIME-1 MISSION SUITE', detail: 'NASA JSC · Integrated subsurface investigation', category: 'volatiles' },
    ],
    dataStatus: 'figma',
    filtered: {
      volatiles: {
        title: 'Nova-C Athena (IM-2)',
        badge: 'ACTIVE DRILL',
        site: 'Mons Mouton (84.8°S, 29.2°E)',
        payload: 'TRIDENT 1m Drill, MSolo, PRIME-1',
        viability: { value: '79 / 100 [OPTIMAL]', tag: 'ENVIRONMENTAL VIABILITY:', accent: true },
      },
    },
  },
  {
    id: 'peregrine',
    payloadSummary: 'NIRVSS, NSS, PITMS',
    index: '03',
    name: 'Peregrine M-1',
    provider: 'Astrobotic',
    lander: 'Peregrine',
    launchWindow: 'Jan 2024',
    site: 'Lacus Mortis',
    target: 'Lacus Mortis, northern near side',
    year: 2024,
    lat: 45.0,
    lon: 25.0,
    ellipseKm: [3, 2],
    slopeDeg: 3.2,
    elevationM: -1800,
    score: 54,
    viability: { windowSunlight: 66, annualSunlight: 52, commsLos: 92, psrKm: 9.4 },
    payloads: [
      { name: 'NIRVSS', detail: 'NASA Ames · Near-infrared volatiles spectrometer system', category: 'spectrometers' },
      { name: 'NSS', detail: 'NASA Ames · Neutron spectrometer for hydrogen mapping', category: 'spectrometers' },
      { name: 'PITMS', detail: 'NASA GSFC · Ion-trap mass spectrometer', category: 'spectrometers' },
    ],
    dataStatus: 'placeholder',
  },
  {
    id: 'griffin-1',
    payloadSummary: 'VIPER Rover',
    index: '04',
    name: 'Griffin-1',
    provider: 'Astrobotic',
    lander: 'Griffin Mission One',
    launchWindow: '2026',
    site: 'Mons Mouton',
    target: 'Mons Mouton Plateau',
    year: 2026,
    lat: -84.9,
    lon: -31.6,
    ellipseKm: [3, 2],
    slopeDeg: 7.2,
    elevationM: 2310,
    score: 68,
    viability: { windowSunlight: 64, annualSunlight: 58, commsLos: 89, psrKm: 3.4 },
    payloads: [
      { name: 'VIPER ROVER', detail: 'NASA Ames · Water-hunting mobile explorer', category: 'rovers' },
    ],
    dataStatus: 'figma',
    filtered: {
      rovers: {
        title: 'Griffin Mission 1',
        badge: 'HEAVY ROVER',
        site: 'Mons Mouton Plateau (84.9°S, 31.6°W)',
        payload: 'VIPER Rover (Water-Hunting Mobile Explorer)',
        viability: { value: '68 / 100 [RUNNER-UP]', tag: 'ENVIRONMENTAL VIABILITY:' },
      },
    },
  },
  {
    id: 'bg-1',
    payloadSummary: 'LuSEE-Night, LISTER',
    index: '05',
    name: 'Blue Ghost M-1',
    provider: 'Firefly Aerospace',
    lander: 'Blue Ghost',
    launchWindow: 'Jan 2025',
    site: 'Mare Crisium',
    target: 'Mare Crisium, near side',
    year: 2025,
    lat: 18.6,
    lon: 61.8,
    ellipseKm: [3.5, 2],
    slopeDeg: 2.4,
    elevationM: -2600,
    score: 57,
    viability: { windowSunlight: 71, annualSunlight: 55, commsLos: 94, psrKm: 11.2 },
    payloads: [
      { name: 'LuSEE-Night', detail: 'NASA / DOE · Radio spectrometer for the lunar night', category: 'other' },
      { name: 'LISTER', detail: 'NASA · Subsurface thermal probe', category: 'other' },
    ],
    dataStatus: 'placeholder',
  },
  {
    id: 'bg-2',
    payloadSummary: 'MSFC Drill, PROSPECT',
    index: '06',
    name: 'Blue Ghost M-2',
    provider: 'Firefly Aerospace',
    lander: 'Blue Ghost',
    launchWindow: '2026',
    site: 'Schrödinger',
    target: 'Schrödinger Basin, far-side polar',
    year: 2026,
    lat: -75.0,
    lon: 132.4,
    ellipseKm: [3, 2],
    slopeDeg: 5.4,
    elevationM: -1100,
    score: 63,
    viability: { windowSunlight: 61, annualSunlight: 57, commsLos: 38, psrKm: 4.9 },
    payloads: [
      { name: 'MSFC DRILL', detail: 'NASA MSFC · Regolith coring drill', category: 'volatiles' },
      { name: 'PROSPECT PACKAGE', detail: 'ESA · Drill and sample analysis laboratory', category: 'volatiles' },
    ],
    dataStatus: 'placeholder',
    filtered: {
      volatiles: {
        title: 'Blue Ghost M-2',
        badge: 'FAR-SIDE POLAR',
        site: 'Schrödinger Basin (75.0°S, 132.4°E)',
        payload: 'MSFC Drill, PROSPECT Package',
      },
    },
  },
  {
    id: 'xl-1',
    payloadSummary: 'TAUBER, BSE-1',
    index: '07',
    name: 'XL-1',
    provider: 'Masten Space',
    lander: 'XL-1 Lander',
    launchWindow: '2026',
    site: 'Haworth Crater',
    target: 'Haworth Crater, south pole',
    year: 2026,
    lat: -87.0,
    lon: -40.0,
    ellipseKm: [3, 2],
    slopeDeg: 5.9,
    elevationM: -400,
    score: 58,
    viability: { windowSunlight: 52, annualSunlight: 44, commsLos: 66, psrKm: 0.9 },
    payloads: [
      { name: 'TAUBER', detail: 'Mobile surface demonstration payload', category: 'rovers' },
      { name: 'BSE-1', detail: 'Surface experiment package', category: 'other' },
    ],
    dataStatus: 'placeholder',
    filtered: {
      rovers: {
        title: 'XL-1 Lander',
        badge: 'MOBILE DEMO',
        site: 'Haworth Crater (-87.0°S, -40.0°W)',
        payload: 'TAUBER Mobile Demo, BSE-1',
      },
    },
  },
  {
    id: 'ls-1',
    payloadSummary: 'LASSI, PRIME-2',
    index: '08',
    name: 'LS-1',
    provider: 'LunaSonde',
    lander: 'LS-1 Lander',
    launchWindow: '2027',
    site: 'Nobile Rim',
    target: 'Nobile crater rim, south pole',
    year: 2027,
    lat: -85.2,
    lon: 53.0,
    ellipseKm: [3, 2],
    slopeDeg: 5.1,
    elevationM: 2050,
    score: 66,
    viability: { windowSunlight: 69, annualSunlight: 61, commsLos: 74, psrKm: 2.3 },
    payloads: [
      { name: 'LASSI', detail: 'Laser spectrometer for surface volatiles', category: 'spectrometers' },
      { name: 'PRIME-2', detail: 'NASA · Follow-on subsurface drill suite', category: 'volatiles' },
    ],
    dataStatus: 'placeholder',
    filtered: {
      volatiles: {
        title: 'LS-1',
        badge: 'POLAR DRILL',
        site: 'Nobile Rim (85.2°S, 53.0°E)',
        payload: 'LASSI, PRIME-2',
      },
    },
  },
]

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

export function missionsFor(filter: MissionFilter, sourceList: Mission[] = missions): Mission[] {
  const list = sourceList.filter((m) => matchesFilter(m, filter))
  // Filtered manifests lead with the featured mission (Figma ordering).
  const lead = filter === 'volatiles' ? 'im-2' : filter === 'rovers' ? 'griffin-1' : undefined
  return lead ? [...list].sort((a, b) => (a.id === lead ? -1 : b.id === lead ? 1 : 0)) : list
}

const ID_ALIASES: Record<string, string> = {
  'clps-prime-1-im2': 'im-2',
  'clps-to2-im-im1': 'im-1',
  'clps-to2-ab-peregrine-1': 'peregrine',
  'clps-to20a-griffin-1': 'griffin-1',
  'clps-to19d-blue-ghost-1': 'bg-1',
  'blue-ghost-1': 'bg-1',
  'clps-cp12-draper': 'bg-2',
  'apolloridge': 'bg-2',
  'clps-cp11-im3': 'xl-1',
  'shackleton': 'xl-1',
  'clps-cp22-im4': 'ls-1',
  'faustini': 'ls-1',
}

export function getMission(id: string, sourceList: Mission[] = missions): Mission {
  const match = sourceList.find((m) => m.id === id) || missions.find((m) => m.id === id)
  if (match) return match
  const alias = ID_ALIASES[id]
  if (alias) {
    const aliasMatch = sourceList.find((m) => m.id === alias) || missions.find((m) => m.id === alias)
    if (aliasMatch) return aliasMatch
  }
  return sourceList[0] || missions[0]
}

/** Rating label for the score badge. */
export function scoreTag(score: number): string {
  if (score >= 75) return 'OPTIMAL_SITE'
  if (score >= 60) return 'VIABLE_SITE'
  return 'MARGINAL_SITE'
}

/** Bar fill (0..100) for each viability input. Distance is inverted: closer is better. */
export function psrFill(km: number): number {
  return Math.max(0, Math.min(100, Math.round(100 - (km / 10) * 100)))
}

export function formatCoords(lat: number, lon: number): string {
  const ns = lat < 0 ? 'S' : 'N'
  const e = ((lon % 360) + 360) % 360
  return `${Math.abs(lat).toFixed(2)}°${ns}, ${e.toFixed(2)}°E`
}
