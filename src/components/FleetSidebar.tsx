import { useState } from 'react'
import type { Mission, MissionFilter } from '../data/missions'
import './FleetSidebar.css'

interface FleetSidebarProps {
  filter: MissionFilter
  missions: Mission[]
  activeId: string
  onSelect: (id: string) => void
}

type CardFilter = 'volatiles' | 'rovers'

const filterCopy: Record<Exclude<MissionFilter, 'all'>, { title: string; subtitle: string; footer: [string, string, boolean][] }> = {
  volatiles: {
    title: '01 // CLPS VOLATILES & DRILLS MANIFEST',
    subtitle: '3 TARGETS IN COLD TRAP & PSR REGIONS',
    footer: [
      ['TARGET VOLATILE SUBSTANCE:', 'H2O ICE / OH RADICALS', false],
      ['CORING DEPTH CAPABILITY:', '1.0m (PERCUSSIVE AUGER)', false],
    ],
  },
  spectrometers: {
    title: '01 // CLPS SPECTROMETERS MANIFEST',
    subtitle: 'MISSIONS CARRYING SPECTROMETER PAYLOADS',
    footer: [
      ['PRIMARY MEASUREMENT:', 'VOLATILE COMPOSITION', false],
      ['TECHNIQUES:', 'MASS SPEC / NEUTRON / NIR', false],
    ],
  },
  rovers: {
    title: '01 // CLPS ROVERS & MOBILITY MANIFEST',
    subtitle: '2 SURFACE MOBILITY & ROVER SYSTEMS',
    footer: [
      ['TRAVERSE RANGE RATING:', '20+ km (SURFACE ODOMETRY)', false],
      ['DIRECT COMMS TO DSN:', '89.0% LOS AVAILABILITY', true],
    ],
  },
}

export function FleetSidebar({ filter, missions, activeId, onSelect }: FleetSidebarProps) {
  const copy = filter === 'all' ? null : filterCopy[filter]
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
          <p className="section-title">{copy ? copy.title : '01 // CLPS ACTIVE FLEET MANIFEST'}</p>
          {copy && <span className="badge">FILTER ACTIVE</span>}
        </div>
        <p className="fleet__subtitle">{copy ? copy.subtitle : `${missions.length} MISSIONS DISPLAYED`}</p>
      </div>

      <ul className="fleet__list">
        {missions.map((mission, i) =>
          filter === 'all' || filter === 'spectrometers' ? (
            <AllCard key={mission.id} mission={mission} active={mission.id === activeId} onSelect={onSelect} />
          ) : (
            <FilteredCard
              key={mission.id}
              mission={mission}
              filter={filter as CardFilter}
              position={String(i + 1).padStart(2, '0')}
              active={mission.id === activeId}
              onSelect={onSelect}
            />
          ),
        )}
      </ul>

      {copy && (
        <div className="fleet__footer">
          {copy.footer.map(([label, value, accent]) => (
            <div className="fleet__footer-row" key={label}>
              <span>{label}</span>
              <span className={accent ? 'fleet__accent' : undefined}>{value}</span>
            </div>
          ))}
        </div>
      )}
    </aside>
  )
}

interface CardProps {
  mission: Mission
  active: boolean
  onSelect: (id: string) => void
}

function AllCard({ mission, active, onSelect }: CardProps) {
  return (
    <li>
      <button
        type="button"
        className={`card${active ? ' card--active' : ''}`}
        onClick={() => onSelect(mission.id)}
        aria-current={active}
      >
        <div className="card__head">
          <span className="card__index">{mission.index}</span>
          <span className="card__name">{mission.name}</span>
          {active && <span className="badge card__badge">ACTIVE</span>}
        </div>
        <dl className="card__rows">
          <Row label="PROVIDER" value={mission.provider} bright />
          <Row label="SITE" value={mission.site} bright />
          <Row label="PAYLOAD" value={mission.payloadSummary} />
          <Row label="YEAR" value={String(mission.year)} bright />
        </dl>
      </button>
    </li>
  )
}

function FilteredCard({
  mission,
  filter,
  position,
  active,
  onSelect,
}: CardProps & { filter: CardFilter; position: string }) {
  const data = mission.filtered?.[filter]
  if (!data) return null

  return (
    <li>
      <button
        type="button"
        className={`card card--filtered${active ? ' card--active card--flagged' : ''}`}
        onClick={() => onSelect(mission.id)}
        aria-current={active}
      >
        <div className="card__head">
          <span className="card__index">{position}</span>
          <span className="card__name">{data.title}</span>
          <span className={`badge card__badge${active ? '' : ' badge--neutral'}`}>{data.badge}</span>
        </div>
        <dl className="card__rows card__rows--wide">
          <Row label="PROVIDER" value={mission.provider} bright />
          <Row label="SITE" value={data.site} bright />
          <Row label="PAYLOAD" value={data.payload} accent={active} bright={!active} />
          <Row label="YEAR" value={String(mission.year)} bright />
        </dl>
        {active && data.viability && (
          <div className="card__viability">
            <span>{data.viability.tag}</span>
            <span className={data.viability.accent ? 'fleet__accent' : undefined}>{data.viability.value}</span>
          </div>
        )}
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
