// React 18+ automatic JSX runtime
import './TimelineScrubber.css'

export interface TrackData {
  schema: string
  latitude_deg: number
  longitude_deg: number
  start_utc: string
  duration_days: number
  step_minutes: number
  samples: number
  sunlit_percent: number
  earth_los_percent: number
  columns: {
    utc: string[]
    hours_from_start: number[]
    sun_elevation_deg: number[]
    sun_azimuth_deg: number[]
    sun_terrain_horizon_deg: number[]
    sun_is_lit: boolean[]
    sun_disk_visible_fraction: number[]
    earth_elevation_deg: number[]
    earth_azimuth_deg: number[]
    earth_direct_los: boolean[]
    earth_round_trip_light_time_s: number[]
    sun_unit_moon_pa: [number, number, number][]
    earth_unit_moon_pa: [number, number, number][]
  }
}

interface TimelineScrubberProps {
  track: TrackData | null
  currentHour: number
  onChangeHour: (hour: number) => void
  isPlaying: boolean
  onTogglePlay: () => void
  missionName?: string
}

export function TimelineScrubber({
  track,
  currentHour,
  onChangeHour,
  isPlaying,
  onTogglePlay,
  missionName,
}: TimelineScrubberProps) {
  if (!track || !track.columns || track.columns.hours_from_start.length === 0) {
    return null
  }

  const maxHour = track.columns.hours_from_start[track.columns.hours_from_start.length - 1] || 708
  const clampedHour = Math.max(0, Math.min(maxHour, Math.round(currentHour)))
  const currentUtc = track.columns.utc[clampedHour] || track.start_utc
  const isLit = track.columns.sun_is_lit[clampedHour] ?? true
  const earthLos = track.columns.earth_direct_los[clampedHour] ?? true
  const sunElev = track.columns.sun_elevation_deg[clampedHour] ?? 0.0
  const earthElev = track.columns.earth_elevation_deg[clampedHour] ?? 0.0

  const days = Math.floor(clampedHour / 24)
  const hours = clampedHour % 24
  // progress percentage
  const progressPct = ((clampedHour / maxHour) * 100).toFixed(2)

  return (
    <div className="scrubber-panel" role="region" aria-label="29.5-day synodic month timeline scrubber">
      <div className="scrubber-panel__header">
        <div className="scrubber-panel__title">
          <span className="scrubber-panel__dot" />
          <strong>SYNODIC MONTH SCRUBBER (29.5d)</strong>
          <span className="scrubber-panel__mission">{missionName || 'CLPS TRACK'} ({progressPct}%)</span>
        </div>
        <div className="scrubber-panel__telemetry">
          <span className={`telemetry-pill ${isLit ? 'telemetry-pill--sun' : 'telemetry-pill--shadow'}`}>
            ☉ SUN: {sunElev >= 0 ? `+${sunElev.toFixed(1)}°` : `${sunElev.toFixed(1)}°`} [{isLit ? 'LIT' : 'SHADOW'}]
          </span>
          <span className={`telemetry-pill ${earthLos ? 'telemetry-pill--earth' : 'telemetry-pill--occulted'}`}>
            ⊕ EARTH: {earthElev >= 0 ? `+${earthElev.toFixed(1)}°` : `${earthElev.toFixed(1)}°`} [{earthLos ? 'DTE ACTIVE' : 'OCCULTED'}]
          </span>
        </div>
      </div>

      <div className="scrubber-panel__controls">
        <button
          type="button"
          className={`scrubber-play-btn ${isPlaying ? 'scrubber-play-btn--active' : ''}`}
          onClick={onTogglePlay}
          title={isPlaying ? 'Pause 60 FPS animation' : 'Play synodic month orbital cycle'}
        >
          {isPlaying ? '⏸ PAUSE' : '▶ PLAY 29.5d'}
        </button>

        <div className="scrubber-track-wrapper">
          {/* Dual illumination ribbon showing light/shadow and comms intervals */}
          <div className="scrubber-ribbon" title="Top: Solar Illumination · Bottom: Earth Line-of-Sight">
            <svg className="scrubber-ribbon__svg" viewBox={`0 0 ${track.columns.hours_from_start.length} 10`} preserveAspectRatio="none">
              {track.columns.sun_is_lit.map((lit, i) => (
                <rect
                  key={`s-${i}`}
                  x={i}
                  y={0}
                  width={1}
                  height={5}
                  fill={lit ? '#ffbb00' : '#1a2233'}
                />
              ))}
              {track.columns.earth_direct_los.map((los, i) => (
                <rect
                  key={`e-${i}`}
                  x={i}
                  y={5}
                  width={1}
                  height={5}
                  fill={los ? '#00e5ff' : '#441122'}
                />
              ))}
            </svg>
          </div>

          <input
            type="range"
            min={0}
            max={maxHour}
            step={1}
            value={clampedHour}
            onChange={(e) => onChangeHour(Number(e.target.value))}
            className="scrubber-slider"
            aria-label="Mission synodic hour"
          />
        </div>

        <div className="scrubber-time-badge">
          <span className="scrubber-time-badge__clock">
            T+{days}d {hours.toString().padStart(2, '0')}h
          </span>
          <span className="scrubber-time-badge__utc">{currentUtc.replace('T', ' ').replace('Z', ' UTC')}</span>
        </div>
      </div>
    </div>
  )
}
