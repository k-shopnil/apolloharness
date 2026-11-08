import { filterTabs, missionsFor, type Mission, type MissionFilter } from '../data/missions'
import './Header.css'

interface HeaderProps {
  missions: Mission[]
  filter: MissionFilter
  onFilterChange: (filter: MissionFilter) => void
}

export function Header({ missions, filter, onFilterChange }: HeaderProps) {
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

      <div className="header__status" title="NASA PDS · OFFLINE CACHED">
        <span className="header__status-dot" />
        <span className="header__status-text">NASA PDS · OFFLINE CACHED</span>
      </div>
    </header>
  )
}
