import type { UIMode } from './SiteHud'
import brandMark from '../assets/apollo-harness-mark.png'
import teamEmblem from '../gateway/assets/chhaya_spinning_logo.svg'
import teamWordmark from '../gateway/assets/chhaya_type.svg'
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

        <div className="header__status" title="Mission catalog and tracks are bundled with the app; no live server is used">
          <span className="header__status-dot" />
          <span className="header__status-text">Offline data</span>
        </div>

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
