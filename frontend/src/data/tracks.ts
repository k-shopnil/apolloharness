import { useEffect, useState } from 'react'
import { DATA_BASE } from './missions'

/** Columns of a precomputed 29.5-day geometry track (709 hourly samples). */
export interface TrackColumns {
  utc: string[]
  hours_from_start: number[]
  sun_elevation_deg: number[]
  sun_azimuth_deg: number[]
  sun_terrain_horizon_deg: (number | null)[]
  sun_lit: (boolean | null)[]
  sun_disk_visible_fraction: (number | null)[]
  earth_elevation_deg: number[]
  earth_azimuth_deg: number[]
  earth_terrain_horizon_deg: (number | null)[]
  earth_los: (boolean | null)[]
  [extra: string]: unknown[]
}

export interface Track {
  schema: string
  start_utc: string
  step_minutes: number
  samples: number
  horizon_model: 'lola_terrain_mask' | 'spherical_horizon'
  sunlit_percent: number | null
  earth_los_percent: number | null
  mean_sun_disk_visible_fraction: number | null
  sun_partially_blocked_percent: number | null
  earth_partially_blocked_percent: number | null
  columns: TrackColumns
}

export interface TrackFile {
  mission_id: string
  terrain: {
    elevation_m: number | null
    dem_product: string | null
    source_dataset?: string | null
    horizon_model: string
    status: string
  }
  psr: {
    status: string
    distance_km: number | null
    inside_psr: boolean | null
  } | null
  track: Track
}

export interface TrackIndexEntry {
  mission_id: string
  status: string
  file?: string
  window_start_utc?: string
  horizon_model?: string
}

const REASONS: Record<string, string> = {
  skipped_no_coordinate: 'No landing coordinate has been published for this mission.',
  skipped_no_exact_date: 'No exact landing date has been published, so no time window can be computed.',
  skipped_mission_terminated: 'This mission was terminated.',
}

export function trackReason(status: string): string {
  return REASONS[status] ?? `No precomputed track (${status.replace(/_/g, ' ')}).`
}

let indexPromise: Promise<Map<string, TrackIndexEntry>> | null = null

export function loadTrackIndex(): Promise<Map<string, TrackIndexEntry>> {
  indexPromise ??= fetch(`${DATA_BASE}precomputed/tracks/index.json`)
    .then((r) => {
      if (!r.ok) throw new Error(`track index: HTTP ${r.status}`)
      return r.json() as Promise<{ missions: TrackIndexEntry[] }>
    })
    .then((j) => new Map(j.missions.map((m) => [m.mission_id, m])))
    .catch((e) => {
      indexPromise = null
      throw e
    })
  return indexPromise
}

const fileCache = new Map<string, Promise<TrackFile>>()

export function loadTrack(file: string): Promise<TrackFile> {
  let p = fileCache.get(file)
  if (!p) {
    p = fetch(`${DATA_BASE}precomputed/tracks/${file}`).then((r) => {
      if (!r.ok) throw new Error(`${file}: HTTP ${r.status}`)
      return r.json() as Promise<TrackFile>
    })
    p.catch(() => fileCache.delete(file))
    fileCache.set(file, p)
  }
  return p
}

export type TrackLookup =
  | { state: 'loading' }
  | { state: 'ready'; data: TrackFile }
  | { state: 'none'; reason: string }
  | { state: 'error'; reason: string }

/** Loads the precomputed track for a mission, or explains why there is none. */
export function useTrack(missionId: string | null): TrackLookup {
  const [result, setResult] = useState<{ id: string | null; lookup: TrackLookup }>({
    id: null,
    lookup: { state: 'loading' },
  })

  useEffect(() => {
    if (!missionId) return
    let cancelled = false
    const done = (lookup: TrackLookup) => !cancelled && setResult({ id: missionId, lookup })
    loadTrackIndex()
      .then(async (index) => {
        const entry = index.get(missionId)
        if (!entry) return done({ state: 'none', reason: 'This mission is not in the track index.' })
        if (entry.status !== 'complete' || !entry.file) return done({ state: 'none', reason: trackReason(entry.status) })
        done({ state: 'ready', data: await loadTrack(entry.file) })
      })
      .catch((e: Error) => done({ state: 'error', reason: e.message }))
    return () => {
      cancelled = true
    }
  }, [missionId])

  if (!missionId) return { state: 'none', reason: 'No mission selected.' }
  return result.id === missionId ? result.lookup : { state: 'loading' }
}

/** Label for how the skyline was computed; the unmodelled case must say so plainly. */
export function horizonLabel(model: string): string {
  return model === 'lola_terrain_mask' ? 'LOLA terrain horizon' : model === 'spherical_horizon' ? 'Terrain not modelled here' : model
}

export function fmtPct(v: number | null | undefined): string {
  return v === null || v === undefined ? 'Unavailable' : `${v.toFixed(1)}%`
}
