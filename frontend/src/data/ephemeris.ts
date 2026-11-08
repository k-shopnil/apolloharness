import type { LocatedMission } from './missions'
import { unitToLatLon, type TrackSample } from './timeline'

/** Selenographic direction (degrees) of a body as seen from the Moon. */
export interface BodyDirection {
  lat: number
  lon: number
}

export interface Ephemeris {
  subEarth: BodyDirection
  subSolar: BodyDirection
}

/** Sub-Earth / sub-solar directions from the track's body-fixed unit vectors; null if the track lacks them. */
export function ephemerisFrom(sample: TrackSample | null): Ephemeris | null {
  if (!sample?.sunUnit || !sample.earthUnit) return null
  return { subEarth: unitToLatLon(sample.earthUnit), subSolar: unitToLatLon(sample.sunUnit) }
}

export type PowerRating = 'FULL SUN' | 'PARTIAL SUN' | 'NO SUN' | 'UNKNOWN'
export type CommsStatus = 'LINK ACTIVE' | 'MARGINAL' | 'OCCULTED' | 'UNKNOWN'

export interface SiteTelemetry {
  sunElevDeg: number
  power: PowerRating
  earthElevDeg: number
  comms: CommsStatus
  /** True when Earth is above the terrain horizon (direct line of sight). */
  losActive: boolean
}

/** Plain-language status from the engine's own flags: no invented thresholds. */
export function siteTelemetry(_mission: LocatedMission, s: TrackSample): SiteTelemetry {
  const power: PowerRating =
    s.sunLit === null
      ? 'UNKNOWN'
      : !s.sunLit
        ? 'NO SUN'
        : s.sunDiskFraction !== null && s.sunDiskFraction < 1
          ? 'PARTIAL SUN'
          : 'FULL SUN'
  const comms: CommsStatus =
    s.earthLos === null
      ? 'UNKNOWN'
      : !s.earthLos
        ? 'OCCULTED'
        : s.earthDiskFraction !== null && s.earthDiskFraction < 1
          ? 'MARGINAL'
          : 'LINK ACTIVE'
  return {
    sunElevDeg: s.sunElevationDeg,
    power,
    earthElevDeg: s.earthElevationDeg,
    comms,
    losActive: s.earthLos === true,
  }
}
