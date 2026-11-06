/**
 * ApolloHarness Frontend API Service Layer
 * Connects to the FastAPI backend with offline fixture fallback and type safety.
 */
import { missions as staticMissions, type Mission, type Viability } from '../data/missions'
import { fetchSiteGeometry, type SiteGeometry } from './siteGeometry'

export const API_BASE_URL =
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_URL) || 'http://localhost:8000'

export interface HealthResponse {
  status: string
  app_name: string
  mode: 'live' | 'mock'
  offline: boolean
  missions_count: number
}

export interface BackendMission {
  id: string
  name: string
  lat: number
  lon: number
  target?: string
  description?: string
  start_date?: string
  end_date?: string
  score?: number
  viability?: Viability
  landing_ellipse?: {
    semi_major_km: number
    semi_minor_km: number
    azimuth_deg?: number
  }
  payload_instruments?: Array<{
    name: string
    type: string
    description?: string
  }>
}

export interface TacticalSunlight {
  percentage: number
  sunlight_hours: number
  window_days: number
  description: string
}

export interface StrategicSunlight {
  percentage: number
  annual_sunlight_fraction: number
  description: string
}

export interface ViabilityScores {
  solar_viability: number
  earth_comms_viability: number
  ice_proximity_viability: number
  total_viability_score: number
  hard_gate_triggered: boolean
}

export interface SiteScoreResponse {
  lat: number
  lon: number
  target: string
  tactical_mission_sunlight: TacticalSunlight
  strategic_annual_baseline: StrategicSunlight
  scores: ViabilityScores
  hard_gate_rule: Record<string, unknown>
  viability_score: number
  tactical_mission_sunlight_percent: number
  strategic_annual_baseline_percent: number
  comms_uptime_percent: number
  psr_distance_m: number
  psr_distance_km: number
  data_mode?: 'live' | 'mock'
}

export interface SiteCommsResponse {
  lat: number
  lon: number
  earth_comms_viability: number
  earth_visible_fraction?: number
  direct_possible?: boolean
  direct_to_earth_possible?: boolean
  communications_uptime_percent?: number
  longest_blackout_hours?: number
  avg_elevation_deg?: number
  min_elevation_deg?: number
  max_elevation_deg?: number
  total_hours?: number
  visible_hours?: number
  total_hours_evaluated?: number
  start_date?: string
  end_date?: string
  data_mode?: 'live' | 'mock'
}

export interface EndpointTestResult {
  endpoint: string
  url: string
  status: 'PENDING' | 'PASS' | 'FAIL'
  statusCode?: number
  latencyMs?: number
  error?: string
  data?: unknown
}

const scoreCache = new Map<string, SiteScoreResponse>()
const commsCache = new Map<string, SiteCommsResponse>()

export const BACKEND_TO_FRONTEND_ID: Record<string, string> = {
  'clps-prime-1-im2': 'im-2',
  'clps-to2-im-im1': 'im-1',
  'clps-to2-ab-peregrine-1': 'peregrine',
  'clps-to20a-griffin-1': 'griffin-1',
  'clps-to19d-blue-ghost-1': 'bg-1',
  'clps-cp12-draper': 'bg-2',
  'clps-cp11-im3': 'xl-1',
  'clps-cp22-im4': 'ls-1',
  // Direct aliases and fallbacks
  'blue-ghost-1': 'bg-1',
  'shackleton': 'xl-1',
  'apolloridge': 'bg-2',
  'faustini': 'ls-1',
}

/**
 * Check backend service health and runtime mode.
 */
export async function fetchHealth(): Promise<HealthResponse> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 2500)
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/health`, {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    })
    clearTimeout(timer)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch {
    clearTimeout(timer)
    return {
      status: 'offline',
      app_name: 'ApolloHarness (Offline Client)',
      mode: 'mock',
      offline: true,
      missions_count: staticMissions.length,
    }
  }
}

/**
 * Fetch CLPS missions catalog from FastAPI backend with fallback to static missions.
 */
export async function fetchMissions(): Promise<{ missions: Mission[]; mode: 'live' | 'mock' }> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 3000)
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/missions`, {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    })
    clearTimeout(timer)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data: BackendMission[] = await res.json()
    const mode = (res.headers.get('X-Data-Mode') as 'live' | 'mock') || 'live'

    // Merge backend payload with rich frontend UI missions
    const merged: Mission[] = data.map((bm, idx) => {
      const canonicalId = BACKEND_TO_FRONTEND_ID[bm.id] || bm.id
      const match = staticMissions.find((sm) => sm.id === canonicalId || sm.id === bm.id)
      let ellipseKm: [number, number] = match ? match.ellipseKm : [3, 2]
      if (bm.landing_ellipse) {
        const maj = Number(bm.landing_ellipse.semi_major_km) || 3
        const min = Number(bm.landing_ellipse.semi_minor_km) || 2
        ellipseKm = [Math.max(maj, min), Math.min(maj, min)]
      }
      if (match) {
        return {
          ...match,
          id: canonicalId,
          name: bm.name || match.name,
          lat: bm.lat ?? match.lat,
          lon: bm.lon ?? match.lon,
          ellipseKm,
          start_date: bm.start_date,
          end_date: bm.end_date,
          score: bm.score != null ? bm.score : match.score,
          viability: bm.viability
            ? {
                windowSunlight: bm.viability.windowSunlight ?? match.viability.windowSunlight,
                annualSunlight: bm.viability.annualSunlight ?? match.viability.annualSunlight,
                commsLos: bm.viability.commsLos ?? match.viability.commsLos,
                psrKm: bm.viability.psrKm ?? match.viability.psrKm,
              }
            : match.viability,
        }
      }
      // Construct fallback Mission object for any new mission in backend
      const defaultViability: Viability = {
        windowSunlight: 75.0,
        annualSunlight: 50.0,
        commsLos: 80.0,
        psrKm: 2.5,
      }
      return {
        id: bm.id,
        index: String(idx + 1).padStart(2, '0'),
        name: bm.name,
        provider: 'NASA CLPS Partner',
        lander: bm.name,
        launchWindow: bm.start_date || '2026',
        site: bm.target || 'Lunar South Pole',
        target: bm.description || 'Lunar South Pole target region',
        year: bm.start_date ? parseInt(bm.start_date.slice(0, 4), 10) : 2026,
        lat: bm.lat,
        lon: bm.lon,
        ellipseKm: bm.landing_ellipse
          ? [bm.landing_ellipse.semi_major_km, bm.landing_ellipse.semi_minor_km]
          : [4.0, 2.5],
        slopeDeg: 5.5,
        elevationM: 1000,
        score: bm.score != null ? bm.score : 60,
        viability: bm.viability || defaultViability,
        payloadSummary: bm.payload_instruments?.map((p) => p.name).join(', ') || 'Scientific Payload',
        payloads:
          bm.payload_instruments?.map((p) => ({
            name: p.name,
            detail: `${p.type} · ${p.description || 'CLPS instrument'}`,
            category: p.type.toLowerCase().includes('volatile')
              ? 'volatiles'
              : p.type.toLowerCase().includes('spect')
                ? 'spectrometers'
                : 'other',
          })) || [],
        dataStatus: 'placeholder',
      }
    })

    return { missions: merged.length > 0 ? merged : staticMissions, mode }
  } catch {
    clearTimeout(timer)
    return { missions: staticMissions, mode: 'mock' }
  }
}

/**
 * Fetch deterministic site scoring from FastAPI backend.
 */
export async function fetchSiteScore(
  lat: number,
  lon: number,
  startDate?: string,
  endDate?: string,
  permanentlyShadowed = false
): Promise<SiteScoreResponse> {
  const key = `${lat.toFixed(4)},${lon.toFixed(4)},${startDate || ''},${endDate || ''},${permanentlyShadowed}`
  if (scoreCache.has(key)) return scoreCache.get(key)!

  const params = new URLSearchParams({
    lat: lat.toString(),
    lon: lon.toString(),
    permanently_shadowed: permanentlyShadowed.toString(),
  })
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)

  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 2500)
    const res = await fetch(`${API_BASE_URL}/api/v1/sites/score?${params.toString()}`, {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    })
    clearTimeout(timer)
    if (res.ok) {
      const data: SiteScoreResponse = await res.json()
      data.data_mode = (res.headers.get('X-Data-Mode') as 'live' | 'mock') || 'live'
      scoreCache.set(key, data)
      return data
    }
  } catch {
    // fall through to local calculation
  }

  // Analytical local fallback
  const isHardGate = permanentlyShadowed
  const tacticalPct = isHardGate ? 0.0 : Math.max(10.0, Math.min(95.0, 75.0 + (lat + 85.0) * 3.0))
  const commsPct = Math.max(20.0, Math.min(95.0, 70.0 + (lat + 90.0) * 2.0))
  const distKm = Math.max(0.5, Math.abs(lat + 84.8) * 10.0 + 1.2)
  const solarViab = tacticalPct / 100.0
  const commsViab = commsPct / 100.0
  const iceViab = Math.max(0.0, Math.min(1.0, 1.0 - (distKm - 0.5) / 9.5))
  const totalViab = isHardGate ? 0.0 : 0.4 * solarViab + 0.35 * commsViab + 0.25 * iceViab

  const fallback: SiteScoreResponse = {
    data_mode: 'mock',
    lat,
    lon,
    target: 'Moon',
    tactical_mission_sunlight: {
      percentage: tacticalPct,
      sunlight_hours: tacticalPct * 0.24 * 14.0,
      window_days: 14.0,
      description: 'LOLA / LROC illumination model',
    },
    strategic_annual_baseline: {
      percentage: 52.0,
      annual_sunlight_fraction: 0.52,
      description: 'Annual cumulative solar baseline',
    },
    scores: {
      solar_viability: solarViab,
      earth_comms_viability: commsViab,
      ice_proximity_viability: iceViab,
      total_viability_score: totalViab,
      hard_gate_triggered: isHardGate,
    },
    hard_gate_rule: {
      rule: 'tactical_sunlight > 0.0',
      status: isHardGate ? 'TRIGGERED (Score = 0.0)' : 'PASSED',
    },
    viability_score: Math.round(totalViab * 1000) / 10,
    tactical_mission_sunlight_percent: tacticalPct,
    strategic_annual_baseline_percent: 52.0,
    comms_uptime_percent: commsPct,
    psr_distance_m: Math.round(distKm * 1000),
    psr_distance_km: Math.round(distKm * 100) / 100,
  }
  scoreCache.set(key, fallback)
  return fallback
}

/**
 * Fetch communications line-of-sight from FastAPI backend.
 */
export async function fetchSiteComms(
  lat: number,
  lon: number,
  startDate?: string,
  endDate?: string
): Promise<SiteCommsResponse> {
  const key = `${lat.toFixed(4)},${lon.toFixed(4)},${startDate || ''},${endDate || ''}`
  if (commsCache.has(key)) return commsCache.get(key)!

  const params = new URLSearchParams({
    lat: lat.toString(),
    lon: lon.toString(),
  })
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)

  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 2500)
    const res = await fetch(`${API_BASE_URL}/api/v1/sites/comms?${params.toString()}`, {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    })
    clearTimeout(timer)
    if (res.ok) {
      const data: SiteCommsResponse = await res.json()
      data.data_mode = (res.headers.get('X-Data-Mode') as 'live' | 'mock') || 'live'
      commsCache.set(key, data)
      return data
    }
  } catch {
    // fall through
  }

  const fallback: SiteCommsResponse = {
    data_mode: 'mock',
    lat,
    lon,
    earth_comms_viability: 0.82,
    earth_visible_fraction: 0.82,
    direct_possible: true,
    avg_elevation_deg: 5.28,
    min_elevation_deg: 1.1,
    max_elevation_deg: 9.8,
    total_hours_evaluated: 336.0,
    start_date: startDate,
    end_date: endDate,
  }
  commsCache.set(key, fallback)
  return fallback
}

/**
 * Test all 5 FastAPI backend endpoints and report status, latency, and sample data.
 */
export async function testAllEndpoints(): Promise<EndpointTestResult[]> {
  const tests: { name: string; path: string }[] = [
    { name: '01. Health Check', path: '/api/v1/health' },
    { name: '02. Missions Catalog', path: '/api/v1/missions' },
    {
      name: '03. Site Viability Scoring',
      path: '/api/v1/sites/score?lat=-84.80&lon=29.20&start_date=2026-11-01&end_date=2026-11-15',
    },
    {
      name: '04. Site Comms Line-of-Sight',
      path: '/api/v1/sites/comms?lat=-84.80&lon=29.20&start_date=2026-11-01&end_date=2026-11-15',
    },
    {
      name: '05. Site Celestial Geometry',
      path: '/api/v1/sites/geometry?lat=-84.80&lon=29.20&start_date=2026-11-15T12:00:00Z',
    },
  ]

  const results: EndpointTestResult[] = []

  for (const t of tests) {
    const url = `${API_BASE_URL}${t.path}`
    const t0 = performance.now()
    try {
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), 3500)
      const res = await fetch(url, { signal: controller.signal, headers: { Accept: 'application/json' } })
      clearTimeout(timer)
      const latencyMs = Math.round((performance.now() - t0) * 10) / 10
      const json = await res.json()
      results.push({
        endpoint: t.name,
        url: t.path,
        status: res.ok ? 'PASS' : 'FAIL',
        statusCode: res.status,
        latencyMs,
        data: json,
      })
    } catch (err: unknown) {
      const latencyMs = Math.round((performance.now() - t0) * 10) / 10
      results.push({
        endpoint: t.name,
        url: t.path,
        status: 'FAIL',
        statusCode: 0,
        latencyMs,
        error: err instanceof Error ? err.message : String(err),
      })
    }
  }

  return results
}

export { fetchSiteGeometry, type SiteGeometry }

export interface GeometryV1Response {
  schema: string
  source: 'engine' | 'precomputed_track'
  site_id?: string
  mission?: string
  site: {
    latitude_deg: number
    longitude_deg: number
    coordinate_type?: string
  }
  utc: string
  sun: {
    azimuth_deg: number
    elevation_deg: number
    terrain_horizon_deg: number
    is_lit: boolean
    time_to_sunset_hours?: number | null
    time_to_sunset_formatted?: string | null
    time_to_sunrise_hours?: number | null
    time_to_sunrise_formatted?: string | null
    countdown_status?: string
    fraction_of_window_up?: number | null
    angular_radius_deg?: number
    disk_visible_fraction?: number
    unit_vector_moon_pa: [number, number, number]
  }
  earth: {
    azimuth_deg: number
    elevation_deg: number
    terrain_horizon_deg: number
    direct_los: boolean
    time_to_earthset_hours?: number | null
    time_to_earthset_formatted?: string | null
    time_to_earthrise_hours?: number | null
    time_to_earthrise_formatted?: string | null
    countdown_status?: string
    fraction_of_window_up?: number | null
    angular_radius_deg?: number
    disk_visible_fraction?: number
    range_km?: number | null
    round_trip_light_time_s?: number | null
    unit_vector_moon_pa: [number, number, number]
  }
  psr?: {
    distance_m?: number | null
    inside_psr?: boolean | null
    nearest_psr_id?: string | null
    nearest_psr_label?: string | null
    nearest_psr_host?: string | null
    status?: string
  }
  events?: Array<{
    body: 'sun' | 'earth'
    kind: 'rise' | 'set'
    utc: string
    hours_from_start: number
  }>
  horizon_model?: string
  terrain?: {
    elevation_m?: number | null
    dem_product?: string | null
    dem_resolution_m?: number | null
  }
}

export async function fetchGeometryV1(params: {
  site_id?: string
  lat?: number
  lon?: number
  utc?: string
}): Promise<GeometryV1Response | null> {
  const query = new URLSearchParams()
  if (params.site_id) query.set('site_id', params.site_id)
  if (params.lat != null) query.set('lat', params.lat.toString())
  if (params.lon != null) query.set('lon', params.lon.toString())
  if (params.utc) query.set('utc', params.utc)

  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/sites/geometry?${query.toString()}`, {
      headers: { Accept: 'application/json' },
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch {
    if (params.site_id) {
      try {
        const fixtureRes = await fetch(`/offline_fixtures/site_geometry/${params.site_id}.json`)
        if (fixtureRes.ok) return await fixtureRes.json()
      } catch {}
    }
    return null
  }
}

export interface LaunchSlipComparison {
  latitude_deg: number
  longitude_deg: number
  duration_days: number
  horizon_model: string
  date_a: {
    start_utc: string
    sunlit_percent: number
    earth_los_percent: number
    sun: { is_lit: boolean }
  }
  date_b: {
    start_utc: string
    sunlit_percent: number
    earth_los_percent: number
    sun: { is_lit: boolean }
  }
  delta_b_minus_a: {
    sunlit_percent: number
    earth_los_percent: number
    lit_at_arrival_changed: boolean
  }
}

export async function compareLaunchDates(
  siteId: string,
  dateA: string,
  dateB: string,
  durationDays = 14
): Promise<LaunchSlipComparison | null> {
  const query = new URLSearchParams({
    site_id: siteId,
    date_a: dateA,
    date_b: dateB,
    duration_days: durationDays.toString(),
  })
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/sites/compare-dates?${query.toString()}`, {
      headers: { Accept: 'application/json' },
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch {
    return null
  }
}

export async function fetchPrecomputedTrack(siteId: string) {
  try {
    const res = await fetch(`/data/precomputed/tracks/${siteId}.json`)
    if (res.ok) {
      const data = await res.json()
      return data.track || null
    }
  } catch {}
  return null
}

export async function fetchCustomSite(
  lat: number,
  lon: number,
  utc?: string,
  includeTrack = true,
): Promise<any | null> {
  const query = new URLSearchParams({
    lat: lat.toString(),
    lon: lon.toString(),
    include_psr: 'true',
    include_track: includeTrack ? 'true' : 'false',
  })
  if (utc) query.set('utc', utc)
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/sites/custom?${query.toString()}`, {
      headers: { Accept: 'application/json' },
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch {
    return null
  }
}
