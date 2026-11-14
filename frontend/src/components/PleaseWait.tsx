import { useEffect, useState } from 'react'
import { useEngineStatus } from '../data/api'
import { Icon } from './Icon'
import './PleaseWait.css'

interface Props {
  /** What is happening, e.g. "Calculating this point". */
  task: string
  /** Set for work done by the live engine, so a cold start is explained. */
  live?: boolean
  compact?: boolean
}

/**
 * A kind "please wait" with a running timer. For live-engine work it says when
 * the server is waking up: the free host sleeps after 15 idle minutes and takes
 * a while to start again.
 */
export function PleaseWait({ task, live = false, compact = false }: Props) {
  const engine = useEngineStatus()
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    const started = Date.now()
    const id = window.setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000)
    return () => window.clearInterval(id)
  }, [])

  const waking = live && engine === 'waking'
  const slow = seconds >= 8

  return (
    <div className={`wait${compact ? ' wait--compact' : ''}`} role="status" aria-live="polite">
      <p className="wait__line">
        <Icon name="waking" className="wait__spin" />
        <span>
          {waking ? 'Waking up the live engine…' : `${task}…`}
          {seconds >= 2 && <span className="wait__secs"> {seconds}s</span>}
        </span>
      </p>
      {!compact && (
        <p className="wait__why">
          {waking
            ? 'Our free server sleeps when nobody is using it, so the first request after a quiet spell can take up to a minute. Thanks for waiting. Everything already on screen keeps working.'
            : slow
              ? 'This is taking a little longer than usual. Thanks for your patience.'
              : live
                ? 'Computed on request from NASA SPICE and LOLA data. This usually takes a few seconds.'
                : 'Just a moment.'}
        </p>
      )}
    </div>
  )
}
