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
  volatiles: 'Volatiles & drills',
  spectrometers: 'Spectrometers',
  rovers: 'Rovers & mobility',
}

export function FleetSidebar({ filter, missions, group, onGroupChange, activeId, onSelect }: FleetSidebarProps) {
  const title = filter === 'all' ? 'Missions' : filterTitle[filter]
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
        <span>{expanded ? 'Hide missions' : 'Show missions'}</span>
      </button>
      <div className="fleet__header">
        <div className="fleet__title-row">
          <h2 className="fleet__title">{title}</h2>
          <span className="fleet__count">{missions.length}</span>
        </div>
        <div className="segmented" role="group" aria-label="Mission group">
          {groupTabs.map((g) => (
            <button key={g.id} type="button" aria-pressed={group === g.id} onClick={() => onGroupChange(g.id)}>
              {g.label}
            </button>
          ))}
        </div>
      </div>

      <ul className="fleet__list">
        {missions.map((mission) => (
          <MissionCard key={mission.id} mission={mission} active={mission.id === activeId} onSelect={onSelect} />
        ))}
      </ul>
    </aside>
  )
}

interface CardProps {
  mission: Mission
  active: boolean
  onSelect: (id: string) => void
}

function MissionCard({ mission, active, onSelect }: CardProps) {
  const located = mission.lat !== null && mission.lon !== null
  return (
    <li>
      <button
        type="button"
        className={`card${active ? ' card--active' : ''}`}
        onClick={() => onSelect(mission.id)}
        aria-current={active}
      >
        <span className="card__top">
          <span className="card__name">{mission.name}</span>
          <span className="card__year">{missionYear(mission)}</span>
        </span>
        <span className="card__meta">
          {mission.provider} · {mission.targetSite}
        </span>
        <span className={`card__coord${located ? '' : ' card__coord--none'}`}>{coordinateBadge(mission)}</span>
      </button>
    </li>
  )
}
