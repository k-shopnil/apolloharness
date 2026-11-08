import type { Mission } from './missions'

/** Selenographic direction (degrees) of a body as seen from the Moon's centre. */
export interface BodyDirection {
  lat: number
  lon: number
}

/**
 * Local fixtures for the sub-Earth and sub-solar points. These stand in for the
 * ephemeris backend; swap `getEphemeris()` for an API call later without touching the UI.
 * Earth sits near (0, 0) with libration of a few degrees; the Sun is near the equator.
 */
export interface Ephemeris {
  subEarth: BodyDirection
  subSolar: BodyDirection
}

const FIXTURE: Ephemeris = {
  subEarth: { lat: 1.5, lon: 2.0 },
  subSolar: { lat: -1.1, lon: 38.0 },
}

export function getEphemeris(): Ephemeris {
  return FIXTURE
}

const rad = (d: number) => (d * Math.PI) / 180
const deg = (r: number) => (r * 180) / Math.PI

/** Elevation (deg) of a body above the local horizon of a surface point. */
export function elevationDeg(site: BodyDirection, body: BodyDirection): number {
  const s =
    Math.sin(rad(site.lat)) * Math.sin(rad(body.lat)) +
    Math.cos(rad(site.lat)) * Math.cos(rad(body.lat)) * Math.cos(rad(body.lon - site.lon))
  return deg(Math.asin(Math.max(-1, Math.min(1, s))))
}

export type PowerRating = 'NOMINAL' | 'MARGINAL' | 'NO SUN'
export type CommsStatus = 'LINK ACTIVE' | 'LOW ELEVATION' | 'OCCULTED'

export interface SiteTelemetry {
  psrKm: number
  sunElevDeg: number
  power: PowerRating
  earthElevDeg: number
  comms: CommsStatus
  /** True when Earth is above the horizon, i.e. the DTE beam is not blocked by the Moon. */
  losActive: boolean
}

export function siteTelemetry(mission: Mission, eph: Ephemeris = getEphemeris()): SiteTelemetry {
  const site = { lat: mission.lat, lon: mission.lon }
  const sunElevDeg = elevationDeg(site, eph.subSolar)
  const earthElevDeg = elevationDeg(site, eph.subEarth)
  const losActive = earthElevDeg > 0
  return {
    psrKm: mission.viability.psrKm,
    sunElevDeg,
    power: sunElevDeg >= 1.5 ? 'NOMINAL' : sunElevDeg > 0 ? 'MARGINAL' : 'NO SUN',
    earthElevDeg,
    comms: !losActive ? 'OCCULTED' : earthElevDeg < 2 ? 'LOW ELEVATION' : 'LINK ACTIVE',
    losActive,
  }
}
