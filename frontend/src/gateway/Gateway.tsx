import { useEffect, useRef, useState } from 'react'
import '@fontsource/inter/latin-800.css'
import apolloMark from './assets/apollo_mark_white.png'
import chhayaSwirl from './assets/chhaya_spinning_logo.svg'
import chhayaType from './assets/chhaya_type.svg'
import nasaLogo from './assets/nasa.png'
import nsacLogo from './assets/nsac.png'
import './Gateway.css'

// NASA Space Apps Challenge 2026 window. Before it the clock counts down (T-);
// after it, it counts mission elapsed time (T+).
const LAUNCH_UTC = Date.parse('2026-11-13T00:00:00Z')

// Launch sequence timing (ms). The interface mounts at ENTER_AT.
const IGNITION_MS = 220
const ENTER_AT = 1350
const ENTER_AT_REDUCED = 260

type Phase = 'idle' | 'ignition' | 'ascent'

export function Gateway({ onEnter }: { onEnter: () => void }) {
  const [phase, setPhase] = useState<Phase>('idle')
  const timers = useRef<number[]>([])

  useEffect(() => () => timers.current.forEach(clearTimeout), [])

  const takeoff = () => {
    if (phase !== 'idle') return
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduced) {
      setPhase('ascent')
      timers.current.push(window.setTimeout(onEnter, ENTER_AT_REDUCED))
      return
    }
    setPhase('ignition')
    timers.current.push(
      window.setTimeout(() => setPhase('ascent'), IGNITION_MS),
      window.setTimeout(onEnter, ENTER_AT),
    )
  }

  return (
    <div className="gateway" data-phase={phase}>
      <div className="gw-backdrop" aria-hidden="true">
        <iframe
          className="gw-backdrop__frame"
          src="https://vgpu.sh/preview/optimized-black-hole"
          tabIndex={-1}
          title="Relativistic black hole simulation"
        />
      </div>

      <div className="gw-layout">
        <header className="gw-top">
          <button type="button" className="gw-takeoff" onClick={takeoff} disabled={phase !== 'idle'}>
            <span className="gw-rocket" aria-hidden="true">
              <RocketIcon />
              <span className="gw-rocket__flame" />
            </span>
            <span className="gw-takeoff__label">{phase === 'idle' ? 'Takeoff with us' : 'Liftoff'}</span>
          </button>
          <Countdown />
        </header>

        <footer className="gw-footer">
          <div className="gw-brand">
            <div className="gw-brand__swirl">
              <img src={chhayaSwirl} alt="Chhaya Nautical emblem" />
            </div>
            <div className="gw-brand__type">
              <img src={chhayaType} alt="CHHAYA NAUTICAL" />
            </div>
          </div>

          <nav className="gw-badges" aria-label="Project and partners">
            <a href="https://github.com/k-shopnil/apolloharness" target="_blank" rel="noopener noreferrer" title="Apollo Harness on GitHub">
              <img src={apolloMark} alt="Apollo Harness" className="gw-badges__apollo" />
            </a>
            <a href="https://www.nasa.gov/" target="_blank" rel="noopener noreferrer" title="National Aeronautics and Space Administration">
              <img src={nasaLogo} alt="NASA" className="gw-badges__nasa" />
            </a>
            <a
              href="https://www.spaceappschallenge.org/2026/find-a-team/chhayanautical/"
              target="_blank"
              rel="noopener noreferrer"
              title="NASA International Space Apps Challenge 2026"
            >
              <img src={nsacLogo} alt="NASA International Space Apps Challenge" className="gw-badges__nsac" />
            </a>
          </nav>
        </footer>
      </div>

      <div className="gw-veil" aria-hidden="true" />
    </div>
  )
}

function Countdown() {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  const delta = LAUNCH_UTC - now
  const sign = delta > 0 ? '-' : '+'
  const total = Math.floor(Math.abs(delta) / 1000)
  const units: [number, string][] = [
    [Math.floor(total / 86400), 'D'],
    [Math.floor((total % 86400) / 3600), 'H'],
    [Math.floor((total % 3600) / 60), 'M'],
    [total % 60, 'S'],
  ]
  const spoken = `T${sign === '-' ? ' minus' : ' plus'} ${units[0][0]} days ${units[1][0]} hours ${units[2][0]} minutes`

  return (
    <div className="gw-countdown" role="timer" aria-label={spoken}>
      <div className="gw-countdown__t" aria-hidden="true">
        T{sign}
      </div>
      {units.map(([value, unit]) => (
        <div className="gw-countdown__row" key={unit} aria-hidden="true">
          <span className="gw-countdown__val">{String(value).padStart(2, '0')}</span>
          <span className="gw-countdown__unit">{unit}</span>
        </div>
      ))}
    </div>
  )
}

function RocketIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2.6c2.8 2.1 4.3 5.3 4.3 9.2v4.9H7.7v-4.9c0-3.9 1.5-7.1 4.3-9.2z" />
      <circle cx="12" cy="9.6" r="1.7" />
      <path d="M7.7 12.9 5.2 15.7v3.4l2.5-1.5M16.3 12.9l2.5 2.8v3.4l-2.5-1.5" />
      <path d="M10.6 16.7v1.9M13.4 16.7v1.9" />
    </svg>
  )
}
