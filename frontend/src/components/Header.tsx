import type { UIMode } from './SiteHud'
import brandMark from '../assets/apollo-harness-mark.png'
import teamEmblem from '../gateway/assets/chhaya_spinning_logo.svg'
import teamWordmark from '../gateway/assets/chhaya_type.svg'
import { ThinkingOrb } from 'thinking-orbs'
import { Icon } from './Icon'
import { useEngineStatus, wakeEngine, type EngineStatus } from '../data/api'
import { filterTabs, missionsFor, type Mission, type MissionFilter } from '../data/missions'
import './Header.css'
import './Hud.css'

interface HeaderProps {
  mode: UIMode
  onModeChange: (mode: UIMode) => void
  missions: Mission[]
  filter: MissionFilter
  onFilterChange: (filter: MissionFilter) => void
}

const MODE_LABEL: Record<UIMode, string> = { simple: 'Simple', scientific: 'Scientific' }

export function Header({ mode, onModeChange, missions, filter, onFilterChange }: HeaderProps) {
  return (
    <header className="header">
      <a
        className="header__brand"
        href="/"
        aria-label="Apollo Harness: back to the lobby"
        onClick={(e) => {
          // Client-side: Root listens for popstate and swaps back to the gateway.
          if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return
          e.preventDefault()
          window.history.pushState(null, '', '/')
          window.dispatchEvent(new PopStateEvent('popstate'))
        }}
      >
        <img src={brandMark} alt="Apollo Harness" width={157} height={28} />
      </a>

      <nav className="header__tabs" aria-label="Mission filter">
        {filterTabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`header__tab${filter === tab.id ? ' header__tab--active' : ''}`}
            aria-pressed={filter === tab.id}
            onClick={() => onFilterChange(tab.id)}
          >
            {tab.label}
            <span className="header__count">{missionsFor(missions, tab.id).length}</span>
          </button>
        ))}
      </nav>

      <div className="header__end">
        <div className="mode-switch" role="group" aria-label="Interface mode">
          {(['simple', 'scientific'] as const).map((m) => (
            <button key={m} type="button" aria-pressed={mode === m} onClick={() => onModeChange(m)}>
              {MODE_LABEL[m]}
            </button>
          ))}
        </div>

        <EngineBadge />

        <a
          className="header__team"
          href="https://www.spaceappschallenge.org/2026/find-a-team/chhayanautical/"
          target="_blank"
          rel="noopener noreferrer"
          title="Developed by Team Chhayanautical for the NASA Space Apps Challenge 2026"
        >
          <span className="header__team-label">Developed by</span>
          <img className="header__team-emblem" src={teamEmblem} alt="" width={22} height={24} />
          <img className="header__team-type" src={teamWordmark} alt="Team Chhayanautical" width={60} height={22} />
        </a>

        <a
          className="header__github"
          href="https://github.com/k-shopnil/apolloharness"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Apollo Harness source code on GitHub"
          title="Source code on GitHub"
        >
          <GitHubMark />
        </a>
      </div>
    </header>
  )
}

const ENGINE: Record<EngineStatus, { icon: 'server' | 'waking' | 'database'; tone: 'ok' | 'warn' | 'off'; text: string; title: string }> = {
  live: {
    icon: 'server',
    tone: 'ok',
    text: 'Live engine',
    title: 'Connected to the live engine: clicked points and launch dates are computed from NASA SPICE and LOLA data on request. Mission tracks are bundled with the site.',
  },
  waking: {
    icon: 'waking',
    tone: 'warn',
    text: 'Starting live engine…',
    title: 'The live engine sleeps when nobody uses it and takes a moment to start. Everything bundled with the site already works.',
  },
  offline: {
    icon: 'database',
    tone: 'off',
    text: 'Offline data',
    title: 'The live engine is not reachable, so only bundled data is shown (mission catalog and precomputed tracks). Click to try again.',
  },
  disabled: {
    icon: 'database',
    tone: 'off',
    text: 'Offline data',
    title: 'Mission catalog and tracks are bundled with the site; this build has no live engine.',
  },
}

function EngineBadge() {
  const status = useEngineStatus()
  const e = ENGINE[status]
  return (
    <button
      type="button"
      className="header__status"
      data-tone={e.tone}
      data-status={status}
      title={e.title}
      onClick={status === 'offline' ? () => void wakeEngine() : undefined}
      disabled={status !== 'offline'}
    >
      {status === 'waking' ? (
        <ThinkingOrb
          state="connecting"
          size={20}
          theme="dark"
          paused={window.matchMedia('(prefers-reduced-motion: reduce)').matches}
          aria-hidden="true"
        />
      ) : (
        <Icon name={e.icon} className="header__status-icon" />
      )}
      <span className="header__status-text">{e.text}</span>
    </button>
  )
}

/** The official GitHub mark (Primer Octicons "mark-github", MIT), filled with the current text colour. */
function GitHubMark() {
  return (
    <svg viewBox="0 0 24 24" width={18} height={18} fill="currentColor" aria-hidden="true" focusable="false">
      <path d="M10.226 17.284c-2.965-.36-5.054-2.493-5.054-5.256 0-1.123.404-2.336 1.078-3.144-.292-.741-.247-2.314.09-2.965.898-.112 2.111.36 2.83 1.01.853-.269 1.752-.404 2.853-.404 1.1 0 1.999.135 2.807.382.696-.629 1.932-1.1 2.83-.988.315.606.36 2.179.067 2.942.72.854 1.101 2 1.101 3.167 0 2.763-2.089 4.852-5.098 5.234.763.494 1.28 1.572 1.28 2.807v2.336c0 .674.561 1.056 1.235.786 4.066-1.55 7.255-5.615 7.255-10.646C23.5 6.188 18.334 1 11.978 1 5.62 1 .5 6.188.5 12.545c0 4.986 3.167 9.12 7.435 10.669.606.225 1.19-.18 1.19-.786V20.63a2.9 2.9 0 0 1-1.078.224c-1.483 0-2.359-.808-2.987-2.313-.247-.607-.517-.966-1.034-1.033-.27-.023-.359-.135-.359-.27 0-.27.45-.471.898-.471.652 0 1.213.404 1.797 1.235.45.651.921.943 1.483.943.561 0 .92-.202 1.437-.719.382-.381.674-.718.944-.943" />
    </svg>
  )
}
