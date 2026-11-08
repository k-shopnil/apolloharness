import { forwardRef } from 'react'
import type { Mission } from '../data/missions'
import type { SiteTelemetry } from '../data/ephemeris'

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
  const sunTone = t.power === 'NOMINAL' ? 'ok' : t.power === 'MARGINAL' ? 'warn' : 'bad'
  const commsTone = t.comms === 'LINK ACTIVE' ? 'ok' : t.comms === 'LOW ELEVATION' ? 'warn' : 'bad'
  return (
    <div ref={ref} className="site-card" style={{ visibility: 'hidden' }}>
      <div className="site-card__title">{mission.site.toUpperCase()}</div>
      <div className="site-card__row">
        <span>PSR COLD TRAP</span>
        <b>{t.psrKm.toFixed(1)} km</b>
      </div>
      <div className="site-card__row">
        <span>SUN ELEV</span>
        <b>
          {fmt(t.sunElevDeg)} <i data-tone={sunTone}>{t.power}</i>
        </b>
      </div>
      <div className="site-card__row">
        <span>EARTH ELEV</span>
        <b>
          {fmt(t.earthElevDeg)} <i data-tone={commsTone}>{t.comms}</i>
        </b>
      </div>
    </div>
  )
})
