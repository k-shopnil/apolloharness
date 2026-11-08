import type { Track } from './tracks'

type Vec3 = [number, number, number]

/** Track values at one instant, interpolated between hourly samples. */
export interface TrackSample {
  hours: number
  utc: string
  sunElevationDeg: number
  sunAzimuthDeg: number
  sunHorizonDeg: number | null
  /** Elevation minus terrain horizon; positive = above the skyline. */
  sunMarginDeg: number | null
  sunLit: boolean | null
  sunDiskFraction: number | null
  earthElevationDeg: number
  earthAzimuthDeg: number
  earthHorizonDeg: number | null
  earthMarginDeg: number | null
  earthLos: boolean | null
  earthDiskFraction: number | null
  earthRangeKm: number | null
  roundTripS: number | null
  sunUnit: Vec3 | null
  earthUnit: Vec3 | null
}

const lerp = (a: number, b: number, f: number) => a + (b - a) * f

/** Shortest-arc azimuth blend: 359 -> 1 passes through 0, not 180. */
export function lerpAzimuth(a: number, b: number, f: number): number {
  const d = ((b - a + 540) % 360) - 180
  return (a + f * d + 360) % 360
}

function lerpNullable(a: number | null, b: number | null, f: number): number | null {
  return a === null || b === null ? null : lerp(a, b, f)
}

function lerpUnit(a: Vec3 | undefined, b: Vec3 | undefined, f: number): Vec3 | null {
  if (!a || !b) return null
  const v: Vec3 = [lerp(a[0], b[0], f), lerp(a[1], b[1], f), lerp(a[2], b[2], f)]
  const n = Math.hypot(...v) || 1
  return [v[0] / n, v[1] / n, v[2] / n]
}

const margin = (el: number, horizon: number | null) => (horizon === null ? null : el - horizon)

export function trackDurationHours(track: Track): number {
  const h = track.columns.hours_from_start
  return h[h.length - 1] ?? 0
}

export function sampleTrack(track: Track, hours: number): TrackSample {
  const c = track.columns
  const last = c.utc.length - 1
  const t = Math.max(0, Math.min(trackDurationHours(track), hours))
  const stepH = track.step_minutes / 60
  const i = Math.min(last, Math.floor(t / stepH + 1e-9))
  const j = Math.min(last, i + 1)
  const f = j === i ? 0 : (t - c.hours_from_start[i]) / (c.hours_from_start[j] - c.hours_from_start[i])
  const near = f < 0.5 ? i : j
  const sunEl = lerp(c.sun_elevation_deg[i], c.sun_elevation_deg[j], f)
  const earthEl = lerp(c.earth_elevation_deg[i], c.earth_elevation_deg[j], f)
  const sunHorizon = lerpNullable(c.sun_terrain_horizon_deg[i], c.sun_terrain_horizon_deg[j], f)
  const earthHorizon = lerpNullable(c.earth_terrain_horizon_deg[i], c.earth_terrain_horizon_deg[j], f)
  const rtt = c.round_trip_light_time_s as number[] | undefined
  const range = c.earth_range_km as number[] | undefined
  const earthDisk = c.earth_disk_visible_fraction as (number | null)[] | undefined
  const sunVecs = c.sun_unit_moon_pa as Vec3[] | undefined
  const earthVecs = c.earth_unit_moon_pa as Vec3[] | undefined

  return {
    hours: t,
    utc: c.utc[near],
    sunElevationDeg: sunEl,
    sunAzimuthDeg: lerpAzimuth(c.sun_azimuth_deg[i], c.sun_azimuth_deg[j], f),
    sunHorizonDeg: sunHorizon,
    sunMarginDeg: margin(sunEl, sunHorizon),
    sunLit: c.sun_lit[near],
    sunDiskFraction: c.sun_disk_visible_fraction[near],
    earthElevationDeg: earthEl,
    earthAzimuthDeg: lerpAzimuth(c.earth_azimuth_deg[i], c.earth_azimuth_deg[j], f),
    earthHorizonDeg: earthHorizon,
    earthMarginDeg: margin(earthEl, earthHorizon),
    earthLos: c.earth_los[near],
    earthDiskFraction: earthDisk?.[near] ?? null,
    earthRangeKm: range ? lerp(range[i], range[j], f) : null,
    roundTripS: rtt ? lerp(rtt[i], rtt[j], f) : null,
    sunUnit: lerpUnit(sunVecs?.[i], sunVecs?.[j], f),
    earthUnit: lerpUnit(earthVecs?.[i], earthVecs?.[j], f),
  }
}

/** Selenographic lat/lon (degrees) of a body-fixed unit vector. */
export function unitToLatLon(v: Vec3): { lat: number; lon: number } {
  return {
    lat: (Math.asin(Math.max(-1, Math.min(1, v[2]))) * 180) / Math.PI,
    lon: (Math.atan2(v[1], v[0]) * 180) / Math.PI,
  }
}

export interface Countdown {
  /** Hours until the state next flips; null when it does not flip inside the window. */
  hoursToChange: number | null
  /** State now (true = lit / link up); null when unknown. */
  now: boolean | null
}

/** Time from `hours` until the boolean series next flips, read from the track itself. */
export function countdown(track: Track, hours: number, series: 'sun_lit' | 'earth_los'): Countdown {
  const c = track.columns
  const flags = c[series]
  const stepH = track.step_minutes / 60
  const now = flags[Math.min(flags.length - 1, Math.round(hours / stepH))]
  if (now === null) return { hoursToChange: null, now: null }
  const el = series === 'sun_lit' ? c.sun_elevation_deg : c.earth_elevation_deg
  const hz = series === 'sun_lit' ? c.sun_terrain_horizon_deg : c.earth_terrain_horizon_deg
  for (let k = Math.round(hours / stepH) + 1; k < flags.length; k++) {
    if (flags[k] !== null && flags[k] !== now) {
      // Refine inside the hour where the flag flipped: linear zero-crossing of (elevation - horizon).
      let at = c.hours_from_start[k]
      const h0 = hz[k - 1]
      const h1 = hz[k]
      if (h0 !== null && h1 !== null) {
        const m0 = el[k - 1] - h0
        const m1 = el[k] - h1
        if (m0 !== m1 && m0 * m1 <= 0) at = c.hours_from_start[k - 1] + (m0 / (m0 - m1)) * (c.hours_from_start[k] - c.hours_from_start[k - 1])
      }
      return { hoursToChange: Math.max(0, at - hours), now }
    }
  }
  return { hoursToChange: null, now }
}

/** "4d 18h" / "7h 12m" / "36m". */
export function formatHours(h: number): string {
  const totalMin = Math.max(0, Math.round(h * 60))
  const d = Math.floor(totalMin / 1440)
  const hr = Math.floor((totalMin % 1440) / 60)
  const m = totalMin % 60
  if (d > 0) return `${d}d ${hr}h`
  if (hr > 0) return `${hr}h ${m}m`
  return `${m}m`
}
