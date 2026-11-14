import { useEffect, useState, useSyncExternalStore } from 'react'
import type { Track, TrackFile, TrackLookup } from './tracks'

/**
 * Client for the live engine (FastAPI on Render). Everything that can be
 * precomputed (catalog, mission tracks) is bundled with the site; the engine is
 * only called for things nobody precomputed: a clicked point, a chosen date.
 *
 * The engine's URL is public, so it is the default here (.env files are
 * git-ignored to keep secrets out). Override at build time with VITE_API_URL,
 * or set VITE_API_URL= (empty) to build an offline-only site.
 */
const DEFAULT_API = 'https://apolloharness-api.onrender.com'
export const API_BASE = ((import.meta.env.VITE_API_URL as string | undefined) ?? DEFAULT_API).replace(/\/+$/, '')

/** disabled: no engine configured · waking: first contact in progress · live · offline: unreachable */
export type EngineStatus = 'disabled' | 'waking' | 'live' | 'offline'

// A sleeping free-tier instance answers its first request only once it has booted.
const WAKE_TIMEOUT_MS = 90_000
const REQUEST_TIMEOUT_MS = 60_000

let status: EngineStatus = API_BASE ? 'waking' : 'disabled'
let wakePromise: Promise<EngineStatus> | null = null
const listeners = new Set<() => void>()

function setStatus(next: EngineStatus) {
  if (next === status) return
  status = next
  listeners.forEach((fn) => fn())
}

export function useEngineStatus(): EngineStatus {
  return useSyncExternalStore(
    (fn) => {
      listeners.add(fn)
      return () => listeners.delete(fn)
    },
    () => status,
  )
}

async function getJson<T>(path: string, params: Record<string, string | number | boolean>, timeoutMs: number): Promise<T> {
  const url = new URL(`${API_BASE}${path}`)
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)))
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  let res: Response
  try {
    res = await fetch(url, { signal: controller.signal, headers: { Accept: 'application/json' } })
  } catch (e) {
    // Network failure or timeout: the engine is not reachable right now.
    setStatus('offline')
    throw new Error(controller.signal.aborted ? 'The live engine did not answer in time.' : 'The live engine is unreachable.', {
      cause: e,
    })
  } finally {
    window.clearTimeout(timer)
  }
  setStatus('live')
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = (await res.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // keep the status code
    }
    throw new Error(detail)
  }
  return (await res.json()) as T
}

/** Contact the engine once (also wakes a sleeping instance). Safe to call repeatedly. */
export function wakeEngine(): Promise<EngineStatus> {
  if (!API_BASE) return Promise.resolve('disabled')
  if (status === 'live') return Promise.resolve('live')
  if (!wakePromise) {
    setStatus('waking')
    // /api/v1/health, not /health: some browser privacy extensions block URLs ending in
    // "/health" (seen in testing), which would wrongly show the engine as offline.
    wakePromise = getJson<{ status: string }>('/api/v1/health', {}, WAKE_TIMEOUT_MS)
      .then((h) => {
        const next: EngineStatus = h.status === 'healthy' ? 'live' : 'offline'
        setStatus(next)
        return next
      })
      .catch(() => {
        setStatus('offline')
        return 'offline' as EngineStatus
      })
      .finally(() => {
        wakePromise = null
      })
  }
  return wakePromise
}

// ---------- Custom point (/sites/custom) ----------

interface Body {
  azimuth_deg: number
  elevation_deg: number
  terrain_horizon_deg: number | null
  disk_visible_fraction: number | null
  countdown_status: string
  [key: string]: unknown
}

export interface CustomSitePayload {
  schema: string
  source: string
  utc: string
  site: { latitude_deg: number; longitude_deg: number }
  sun: Body & { is_lit: boolean | null; time_to_sunset_formatted: string | null; time_to_sunrise_formatted: string | null }
  earth: Body & {
    direct_los: boolean | null
    time_to_earthset_formatted: string | null
    time_to_earthrise_formatted: string | null
    round_trip_light_time_s: number | null
  }
  events: { body: 'sun' | 'earth'; kind: 'rise' | 'set'; utc: string; hours_from_start: number }[]
  psr: {
    status: string
    distance_km: number | null
    inside_psr: boolean | null
    nearest_psr_label?: string | null
    nearest_psr_host?: string | null
  } | null
  horizon_model: string
  terrain: TrackFile['terrain'] & {
    regional_slope_deg?: number | null
    regional_slope_baseline_m?: number | null
    dem_resolution_m?: number | null
  }
  track: Track
  track_summary: { sunlit_percent: number | null; earth_los_percent: number | null; mean_sun_disk_visible_fraction: number | null }
}

export interface CustomSite {
  payload: CustomSitePayload
  /** The same shape as a precomputed mission track, so the HUD and scrubber reuse it. */
  file: TrackFile
}

export async function fetchCustomSite(lat: number, lon: number, utc: string): Promise<CustomSite> {
  const payload = await getJson<CustomSitePayload>(
    '/api/v1/sites/custom',
    { lat, lon, utc, include_psr: true, include_track: true },
    REQUEST_TIMEOUT_MS,
  )
  return {
    payload,
    file: {
      mission_id: customId(lat, lon),
      terrain: payload.terrain,
      psr: payload.psr,
      track: payload.track,
    },
  }
}

export const customId = (lat: number, lon: number) => `custom:${lat.toFixed(4)},${lon.toFixed(4)}`

export interface CustomRequest {
  lat: number
  lon: number
  /** ISO UTC, e.g. 2026-11-15T12:00:00Z */
  utc: string
}

export type CustomLookup =
  | { state: 'loading' }
  | { state: 'ready'; site: CustomSite }
  | { state: 'error'; reason: string }

/** Fetches a custom point; a newer request supersedes an older one still in flight. */
export function useCustomSite(request: CustomRequest | null, attempt: number): CustomLookup | null {
  const key = request ? `${request.lat},${request.lon},${request.utc},${attempt}` : null
  const [result, setResult] = useState<{ key: string | null; lookup: CustomLookup }>({ key: null, lookup: { state: 'loading' } })

  useEffect(() => {
    if (!request || !key) return
    let cancelled = false
    fetchCustomSite(request.lat, request.lon, request.utc)
      .then((site) => !cancelled && setResult({ key, lookup: { state: 'ready', site } }))
      .catch((e: Error) => !cancelled && setResult({ key, lookup: { state: 'error', reason: e.message } }))
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  if (!request) return null
  return result.key === key ? result.lookup : { state: 'loading' }
}

/** The custom lookup in the same shape as a catalog track lookup (HUD and scrubber reuse it). */
export function asTrackLookup(lookup: CustomLookup): TrackLookup {
  if (lookup.state === 'ready') return { state: 'ready', data: lookup.site.file }
  if (lookup.state === 'error') return { state: 'error', reason: lookup.reason }
  return { state: 'loading' }
}

/** Current time as ISO UTC to the minute. */
export function nowUtc(): string {
  return new Date().toISOString().slice(0, 16) + ':00Z'
}

// ---------- Launch dates (/sites/compare-dates) ----------

export interface DateRun {
  start_utc: string
  sunlit_percent: number | null
  earth_los_percent: number | null
  sun: { is_lit: boolean | null; elevation_deg: number; time_to_sunset_formatted?: string | null; time_to_sunrise_formatted?: string | null }
  earth: { direct_los: boolean | null; elevation_deg: number; time_to_earthset_formatted?: string | null; time_to_earthrise_formatted?: string | null }
  events: CustomSitePayload['events']
  track: { columns: { hours_from_start: number[]; sun_lit: (boolean | null)[]; earth_los: (boolean | null)[]; sun_elevation_deg: number[] } }
}

export interface DateComparison {
  latitude_deg: number
  longitude_deg: number
  duration_days: number
  horizon_model: string
  terrain: { dem_product?: string | null }
  date_a: DateRun
  date_b: DateRun
  delta_b_minus_a: { sunlit_percent: number | null; earth_los_percent: number | null; lit_at_arrival_changed: boolean | null }
}

export function fetchDateComparison(siteId: string, dateA: string, dateB: string, durationDays: number): Promise<DateComparison> {
  return getJson<DateComparison>(
    '/api/v1/sites/compare-dates',
    { site_id: siteId, date_a: dateA, date_b: dateB, duration_days: durationDays },
    REQUEST_TIMEOUT_MS,
  )
}
