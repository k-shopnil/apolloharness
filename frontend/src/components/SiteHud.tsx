import type { Mission } from '../data/missions'
import { countdown, formatHours, type Countdown, type TrackSample } from '../data/timeline'
import type { TrackFile } from '../data/tracks'
import './Hud.css'

export type UIMode = 'simple' | 'scientific'

interface Props {
  mode: UIMode
  mission: Mission
  data: TrackFile
  sample: TrackSample
}

const deg = (v: number | null, d = 1) => (v === null ? 'Unavailable' : `${v.toFixed(d)}°`)
const pct = (v: number | null) => (v === null ? 'Unavailable' : `${Math.round(v * 100)}%`)

/** A flip that never happens inside the window reads "> time left in window". */
function when(hours: number | null, windowLeft: number): string {
  return hours === null ? `> ${formatHours(windowLeft)}` : formatHours(hours)
}

export function SiteHud({ mode, mission, data, sample }: Props) {
  const track = data.track
  const hrs = track.columns.hours_from_start
  const left = hrs[hrs.length - 1] - sample.hours
  const sun = countdown(track, sample.hours, 'sun_lit')
  const earth = countdown(track, sample.hours, 'earth_los')
  return mode === 'simple' ? (
    <SimplePanel sample={sample} sun={sun} earth={earth} left={left} />
  ) : (
    <ScientificPanel mission={mission} data={data} sample={sample} />
  )
}

function SimplePanel({
  sample: s,
  sun,
  earth,
  left,
}: {
  sample: TrackSample
  sun: Countdown
  earth: Countdown
  left: number
}) {
  const solar =
    s.sunLit === null
      ? { tone: 'warn', text: 'UNKNOWN' }
      : !s.sunLit
        ? { tone: 'bad', text: 'NO SUN' }
        : s.sunDiskFraction !== null && s.sunDiskFraction < 1
          ? { tone: 'warn', text: `PARTIAL (${pct(s.sunDiskFraction)} of the Sun visible)` }
          : { tone: 'ok', text: 'FULL' }
  const radio =
    s.earthLos === null
      ? { tone: 'warn', text: 'UNKNOWN' }
      : !s.earthLos
        ? { tone: 'bad', text: 'BLOCKED (Earth below the horizon)' }
        : s.earthDiskFraction !== null && s.earthDiskFraction < 1
          ? { tone: 'warn', text: 'MARGINAL (Earth partly behind terrain)' }
          : { tone: 'ok', text: 'ACTIVE' }
  return (
    <div className="hud" data-mode="simple">
      <div className="hud__cell">
        <span className="hud__label">SUNLIGHT</span>
        <strong className="hud__big">
          {sun.now === null
            ? 'Unavailable'
            : sun.now
              ? `${when(sun.hoursToChange, left)} of sunlight remaining`
              : `Sunrise in ${when(sun.hoursToChange, left)}`}
        </strong>
        <span className="hud__badge" data-tone={solar.tone}>
          SOLAR POWER: {solar.text}
        </span>
      </div>
      <div className="hud__cell">
        <span className="hud__label">EARTH CONTACT</span>
        <strong className="hud__big">
          {earth.now === null
            ? 'Unavailable'
            : earth.now
              ? `Direct Earth contact: ACTIVE · ends in ${when(earth.hoursToChange, left)}`
              : `Direct Earth contact: LOST · returns in ${when(earth.hoursToChange, left)}`}
        </strong>
        <span className="hud__badge" data-tone={radio.tone}>
          RADIO LINK: {radio.text}
        </span>
        <span className="hud__sub">
          Round-trip ping: {s.roundTripS === null ? 'Unavailable' : `${s.roundTripS.toFixed(2)} s`}
        </span>
      </div>
    </div>
  )
}

function ScientificPanel({ mission, data, sample: s }: { mission: Mission; data: TrackFile; sample: TrackSample }) {
  const vec = (v: [number, number, number] | null) => (v ? v.map((x) => x.toFixed(4)).join(', ') : 'Unavailable')
  const rows: [string, string][] = [
    ['SUN AZ / EL', `${deg(s.sunAzimuthDeg)} / ${deg(s.sunElevationDeg, 2)}`],
    ['SUN HORIZON', deg(s.sunHorizonDeg, 2)],
    ['SUN MARGIN', deg(s.sunMarginDeg, 2)],
    ['SUN DISC VISIBLE', pct(s.sunDiskFraction)],
    ['EARTH AZ / EL', `${deg(s.earthAzimuthDeg)} / ${deg(s.earthElevationDeg, 2)}`],
    ['EARTH HORIZON', deg(s.earthHorizonDeg, 2)],
    ['EARTH MARGIN', deg(s.earthMarginDeg, 2)],
    ['EARTH DISC VISIBLE', pct(s.earthDiskFraction)],
    [
      'RANGE / RTT',
      s.earthRangeKm === null || s.roundTripS === null
        ? 'Unavailable'
        : `${Math.round(s.earthRangeKm).toLocaleString('en-US')} km / ${s.roundTripS.toFixed(3)} s`,
    ],
    ['SUN VECTOR (MOON_PA)', vec(s.sunUnit)],
    ['EARTH VECTOR (MOON_PA)', vec(s.earthUnit)],
    ['HORIZON MODEL', data.track.horizon_model],
    ['DEM PRODUCT', data.terrain.dem_product ?? 'Unavailable'],
  ]
  return (
    <div className="hud hud--sci" data-mode="scientific" aria-label={`Telemetry for ${mission.name}`}>
      {rows.map(([k, v]) => (
        <div className="hud__row" key={k}>
          <span>{k}</span>
          <b>{v}</b>
        </div>
      ))}
    </div>
  )
}
