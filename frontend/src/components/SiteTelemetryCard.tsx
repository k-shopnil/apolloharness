import { forwardRef } from 'react'
import type { Mission } from '../data/missions'
import type { SiteTelemetry } from '../data/ephemeris'
import { Icon } from './Icon'

interface Props {
  mission: Mission
  telemetry: SiteTelemetry
}

const fmt = (n: number) => `${n >= 0 ? '+' : ''}${n.toFixed(1)}°`

/** Floating HUD callout. MoonGlobe moves it with `transform` each frame to track the site. */
export const SiteTelemetryCard = forwardRef<HTMLDivElement, Props>(function SiteTelemetryCard(
  { mission, telemetry: t },
  ref,
) {
  const sunTone = t.power === 'FULL SUN' ? 'ok' : t.power === 'PARTIAL SUN' || t.power === 'UNKNOWN' ? 'warn' : 'bad'
  const commsTone = t.comms === 'LINK ACTIVE' ? 'ok' : t.comms === 'MARGINAL' || t.comms === 'UNKNOWN' ? 'warn' : 'bad'
  return (
    <div ref={ref} className="site-card" style={{ visibility: 'hidden' }}>
      <div className="site-card__title">{mission.targetSite}</div>
      <div className="site-card__row">
        <span className="site-card__label" data-tone={sunTone}>
          <Icon name="sun" size={13} />
          Sun
        </span>
        <b>
          {fmt(t.sunElevDeg)} <i data-tone={sunTone}>{t.power}</i>
        </b>
      </div>
      <div className="site-card__row">
        <span className="site-card__label" data-tone={commsTone}>
          <Icon name="earth" size={13} />
          Earth
        </span>
        <b>
          {fmt(t.earthElevDeg)} <i data-tone={commsTone}>{t.comms}</i>
        </b>
      </div>
    </div>
  )
})
