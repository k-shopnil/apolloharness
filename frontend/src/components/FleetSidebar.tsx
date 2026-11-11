import { useState } from 'react'
import { coordinateBadge, groupTabs, missionYear, type Mission, type MissionFilter, type MissionGroup } from '../data/missions'
import './FleetSidebar.css'

interface FleetSidebarProps {
  filter: MissionFilter
  missions: Mission[]
  group: MissionGroup
  onGroupChange: (group: MissionGroup) => void
  activeId: string
  onSelect: (id: string) => void
}

const filterTitle: Record<Exclude<MissionFilter, 'all'>, string> = {
  volatiles: '01 // VOLATILES & DRILLS PAYLOADS',
  spectrometers: '01 // SPECTROMETER PAYLOADS',
  rovers: '01 // ROVERS & MOBILITY PAYLOADS',
}

export function FleetSidebar({ filter, missions, group, onGroupChange, activeId, onSelect }: FleetSidebarProps) {
  const title = filter === 'all' ? '01 // MISSION MANIFEST' : filterTitle[filter]
  // Phones: the manifest is a bottom sheet that peeks over the globe and expands on demand.
  const [expanded, setExpanded] = useState(false)

  return (
    <aside className={`fleet${expanded ? ' fleet--expanded' : ''}`}>
      <button
        type="button"
        className="fleet__handle"
        aria-expanded={expanded}
        onClick={() => setExpanded((v) => !v)}
      >
        <span className="fleet__grip" />
        <span>{expanded ? 'HIDE MANIFEST' : 'SHOW MANIFEST'}</span>
      </button>
      <div className="fleet__header">
        <div className="fleet__header-row">
          <p className="section-title">{title}</p>
          {filter !== 'all' && <span className="badge">FILTER ACTIVE</span>}
        </div>
        <div className="fleet__groups" role="group" aria-label="Mission group">
          {groupTabs.map((g) => (
            <button key={g.id} type="button" aria-pressed={group === g.id} onClick={() => onGroupChange(g.id)}>
              {g.label}
            </button>
          ))}
        </div>
        <p className="fleet__subtitle">{`${missions.length} MISSIONS DISPLAYED`}</p>
      </div>

      <ul className="fleet__list">
        {missions.map((mission, i) => (
          <MissionCard
            key={mission.id}
            mission={mission}
            position={String(i + 1).padStart(2, '0')}
            active={mission.id === activeId}
            onSelect={onSelect}
          />
        ))}
      </ul>

    </aside>
  )
}

interface CardProps {
  mission: Mission
  position: string
  active: boolean
  onSelect: (id: string) => void
}

function MissionCard({ mission, position, active, onSelect }: CardProps) {
  return (
    <li>
      <button
        type="button"
        className={`card${active ? ' card--active' : ''}`}
        onClick={() => onSelect(mission.id)}
        aria-current={active}
      >
        <div className="card__head">
          <span className="card__index">{position}</span>
          <span className="card__name">{mission.name}</span>
          {active && <span className="badge card__badge">ACTIVE</span>}
        </div>
        <dl className="card__rows">
          <Row label="PROVIDER" value={mission.provider} bright />
          <Row label="SITE" value={mission.targetSite} bright />
          <Row label="PAYLOAD" value={mission.payloadSummary} />
          <Row label="YEAR" value={missionYear(mission)} bright />
          <Row label="COORD" value={coordinateBadge(mission)} />
        </dl>
      </button>
    </li>
  )
}

function Row({ label, value, bright, accent }: { label: string; value: string; bright?: boolean; accent?: boolean }) {
  return (
    <div className="card__row">
      <dt>{label}</dt>
      <dd className={accent ? 'fleet__accent' : bright ? 'card__bright' : undefined}>{value}</dd>
    </div>
  )
}
