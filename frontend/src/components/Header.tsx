import type { UIMode } from './SiteHud'
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

export function Header({ mode, onModeChange, missions, filter, onFilterChange }: HeaderProps) {
  return (
    <header className="header">
      <div className="header__brand">
        <span className="header__dot" />
        <span className="header__name">HARNESSAPOLLO</span>
        <span className="header__tag">{'// CLPS LUNAR BROWSER'}</span>
      </div>

      <nav className="header__tabs" aria-label="Mission filter">
        {filterTabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`header__tab${filter === tab.id ? ' header__tab--active' : ''}`}
            aria-pressed={filter === tab.id}
            onClick={() => onFilterChange(tab.id)}
          >
            {tab.label} ({missionsFor(missions, tab.id).length})
          </button>
        ))}
      </nav>

      <div className="mode-switch" role="group" aria-label="Interface mode">
        {(['simple', 'scientific'] as const).map((m) => (
          <button key={m} type="button" aria-pressed={mode === m} onClick={() => onModeChange(m)}>
            {m.toUpperCase()}
          </button>
        ))}
      </div>

      <div className="header__status" title="Mission catalog and tracks are bundled with the app; no live server is used">
        <span className="header__status-dot" />
        <span className="header__status-text">BUNDLED DATA · OFFLINE</span>
      </div>
    </header>
  )
}
