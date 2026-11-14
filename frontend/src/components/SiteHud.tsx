import type { Mission } from '../data/missions'
import { countdown, formatHours, type Countdown, type TrackSample } from '../data/timeline'
import { horizonLabel, type TrackFile } from '../data/tracks'
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
      ? { tone: 'warn', text: 'Unknown' }
      : !s.sunLit
        ? { tone: 'bad', text: 'No sun' }
        : s.sunDiskFraction !== null && s.sunDiskFraction < 1
          ? { tone: 'warn', text: `Partial, ${pct(s.sunDiskFraction)} of the disc` }
          : { tone: 'ok', text: 'Full' }
  const radio =
    s.earthLos === null
      ? { tone: 'warn', text: 'Unknown' }
      : !s.earthLos
        ? { tone: 'bad', text: 'Blocked, Earth below the horizon' }
        : s.earthDiskFraction !== null && s.earthDiskFraction < 1
          ? { tone: 'warn', text: 'Marginal, Earth partly behind terrain' }
          : { tone: 'ok', text: 'Active' }
  return (
    <div className="hud" data-mode="simple">
      <div className="hud__cell">
        <span className="hud__label">Sunlight</span>
        <strong className="hud__big">
          {sun.now === null
            ? 'Unavailable'
            : sun.now
              ? `${when(sun.hoursToChange, left)} of sunlight left`
              : `Sunrise in ${when(sun.hoursToChange, left)}`}
        </strong>
        <span className="hud__badge" data-tone={solar.tone}>
          Solar power · {solar.text}
        </span>
      </div>
      <div className="hud__cell">
        <span className="hud__label">Earth contact</span>
        <strong className="hud__big">
          {earth.now === null
            ? 'Unavailable'
            : earth.now
              ? `In contact for ${when(earth.hoursToChange, left)}`
              : `Earth returns in ${when(earth.hoursToChange, left)}`}
        </strong>
        <span className="hud__badge" data-tone={radio.tone}>
          Radio link · {radio.text}
        </span>
        <span className="hud__sub">
          Round trip {s.roundTripS === null ? 'Unavailable' : `${s.roundTripS.toFixed(2)} s`}
        </span>
      </div>
    </div>
  )
}

function ScientificPanel({ mission, data, sample: s }: { mission: Mission; data: TrackFile; sample: TrackSample }) {
  const vec = (v: [number, number, number] | null) => (v ? v.map((x) => x.toFixed(4)).join(', ') : 'Unavailable')
  const rows: [string, string][] = [
    ['Sun az / el', `${deg(s.sunAzimuthDeg)} / ${deg(s.sunElevationDeg, 2)}`],
    ['Sun horizon', deg(s.sunHorizonDeg, 2)],
    ['Sun margin', deg(s.sunMarginDeg, 2)],
    ['Sun disc visible', pct(s.sunDiskFraction)],
    ['Earth az / el', `${deg(s.earthAzimuthDeg)} / ${deg(s.earthElevationDeg, 2)}`],
    ['Earth horizon', deg(s.earthHorizonDeg, 2)],
    ['Earth margin', deg(s.earthMarginDeg, 2)],
    ['Earth disc visible', pct(s.earthDiskFraction)],
    [
      'Range / RTT',
      s.earthRangeKm === null || s.roundTripS === null
        ? 'Unavailable'
        : `${Math.round(s.earthRangeKm).toLocaleString('en-US')} km / ${s.roundTripS.toFixed(3)} s`,
    ],
    ['Sun vector (MOON_PA)', vec(s.sunUnit)],
    ['Earth vector (MOON_PA)', vec(s.earthUnit)],
    ['Horizon model', horizonLabel(data.track.horizon_model)],
    ['DEM product', data.terrain.dem_product ?? 'Unavailable'],
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
