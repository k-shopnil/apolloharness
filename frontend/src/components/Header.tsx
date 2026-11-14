import type { UIMode } from './SiteHud'
import brandMark from '../assets/apollo-harness-mark.png'
import teamEmblem from '../gateway/assets/chhaya_spinning_logo.svg'
import teamWordmark from '../gateway/assets/chhaya_type.svg'
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
      <Icon name={e.icon} className="header__status-icon" />
      <span className="header__status-text">{e.text}</span>
    </button>
  )
}
