import { useEffect, useMemo, useRef, useState } from 'react'
import { trackDurationHours } from '../data/timeline'
import type { Track } from '../data/tracks'
import './Hud.css'

interface Props {
  track: Track
  hours: number
  onChange: (hours: number) => void
}

/** One strip of lit/up (green), dark/down (grey) and unknown (hatched) samples. */
function Strip({ label, flags }: { label: string; flags: (boolean | null)[] }) {
  const runs = useMemo(() => {
    const out: { start: number; len: number; v: boolean | null }[] = []
    flags.forEach((v, i) => {
      const last = out[out.length - 1]
      if (last && last.v === v) last.len++
      else out.push({ start: i, len: 1, v })
    })
    return out
  }, [flags])
  return (
    <div className="scrub__strip" aria-label={label}>
      <span className="scrub__strip-label">{label}</span>
      <div className="scrub__strip-bar">
        {runs.map((r) => (
          <i
            key={r.start}
            data-state={r.v === null ? 'unknown' : r.v ? 'on' : 'off'}
            style={{ left: `${(r.start / flags.length) * 100}%`, width: `${(r.len / flags.length) * 100}%` }}
          />
        ))}
      </div>
    </div>
  )
}

export function TimelineScrubber({ track, hours, onChange }: Props) {
  const total = trackDurationHours(track)
  const stepH = track.step_minutes / 60
  const [playing, setPlaying] = useState(false)
  const hoursRef = useRef(hours)
  hoursRef.current = hours

  // Autoplay: ~12 hourly steps per second, looping at the end.
  useEffect(() => {
    if (!playing) return
    const id = window.setInterval(() => {
      const next = hoursRef.current + stepH
      onChange(next > total ? 0 : next)
    }, 80)
    return () => window.clearInterval(id)
  }, [playing, stepH, total, onChange])

  const idx = Math.min(track.columns.utc.length - 1, Math.round(hours / stepH))

  return (
    <div className="scrub" role="group" aria-label="Timeline scrubber">
      <div className="scrub__top">
        <button type="button" className="scrub__play" onClick={() => setPlaying((p) => !p)} aria-pressed={playing}>
          {playing ? '❚❚ PAUSE' : '▶ PLAY'}
        </button>
        <span className="scrub__time">
          DAY {(hours / 24).toFixed(1)} / {(total / 24).toFixed(1)} · {track.columns.utc[idx]}
        </span>
      </div>
      <input
        type="range"
        className="scrub__range"
        min={0}
        max={total}
        step={stepH / 4}
        value={hours}
        aria-label="Time within the 29.5-day window"
        onChange={(e) => {
          setPlaying(false)
          onChange(Number(e.target.value))
        }}
      />
      <Strip label="SUN" flags={track.columns.sun_lit} />
      <Strip label="EARTH" flags={track.columns.earth_los} />
    </div>
  )
}
