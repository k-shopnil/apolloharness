import { filterTabs, missionsFor, type MissionFilter } from '../data/missions'
import './Header.css'

export type UIMode = 'simple' | 'scientific'

interface HeaderProps {
  filter: MissionFilter
  onFilterChange: (filter: MissionFilter) => void
  apiStatus?: { online: boolean; mode: string; count: number }
  onOpenApiInspector?: () => void
  mode?: UIMode
  onModeChange?: (mode: UIMode) => void
  onOpenPinModal?: () => void
}

export function Header({
  filter,
  onFilterChange,
  apiStatus,
  onOpenApiInspector,
  mode = 'simple',
  onModeChange,
  onOpenPinModal,
}: HeaderProps) {
  const isOnline = Boolean(apiStatus?.online)
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
            {tab.label} ({missionsFor(tab.id).length})
          </button>
        ))}
      </nav>

      <div className="header__actions">
        {/* Dual Mode Switcher (Simple vs Scientific) */}
        <div className="header__mode-toggle" role="radiogroup" aria-label="Interface mode">
          <button
            type="button"
            className={`header__mode-btn ${mode === 'simple' ? 'header__mode-btn--active' : ''}`}
            onClick={() => onModeChange?.('simple')}
            title="Simple Mode: Operational countdowns and plain-language status badges"
          >
            SIMPLE
          </button>
          <button
            type="button"
            className={`header__mode-btn ${mode === 'scientific' ? 'header__mode-btn--active' : ''}`}
            onClick={() => onModeChange?.('scientific')}
            title="Scientific Mode: Precision SPICE ephemeris, topocentric elevations, horizon margins, and unit vectors"
          >
            SCIENTIFIC
          </button>
        </div>

        {/* Custom Coordinates Pin-Drop */}
        <button
          type="button"
          className="header__pin-btn"
          onClick={onOpenPinModal}
          title="Drop custom coordinates anywhere on the Moon"
        >
          📍 PIN COORDS
        </button>

        <button
          type="button"
          className={`header__status ${isOnline ? 'header__status--online' : 'header__status--offline'}`}
          title={
            isOnline
              ? 'FastAPI Backend Online — Click to open API Explorer'
              : 'FastAPI Backend Offline — Operating in Standalone NASA PDS Offline Mode'
          }
          onClick={onOpenApiInspector}
        >
          <span className="header__status-dot" />
          <span className="header__status-text">
            {isOnline
              ? `API: LIVE (${apiStatus?.count ?? 16} MISSIONS) · 8000`
              : 'OFFLINE MODE (PDS CACHED)'}
          </span>
          <span className="header__status-cta">{isOnline ? '[API ↗]' : '[OFFLINE ↗]'}</span>
        </button>
      </div>
    </header>
  )
}
