import { useMemo } from 'react'
import { buildComparison, type CompareRow, type CompareSide } from '../data/compare'
import { getMission, missions } from '../data/missions'
import './CompareView.css'

interface CompareViewProps {
  aId: string
  bId: string
  onChange: (aId: string, bId: string) => void
  onBack: () => void
}

export function CompareView({ aId, bId, onChange, onBack }: CompareViewProps) {
  const comparison = useMemo(() => buildComparison(getMission(aId), getMission(bId)), [aId, bId])
  const { a, b, rows, brief, citations } = comparison

  return (
    <div className="compare">
      <div className="compare__inner">
        <div className="compare__bar">
          <button type="button" className="compare__back" onClick={onBack}>
            ◀ BACK TO FLEET
          </button>

          <div className="compare__pickers">
            <Picker label="SITE A" value={aId} other={bId} onChange={(id) => onChange(id, bId)} />
            <span className="compare__vs">VS</span>
            <Picker label="SITE B" value={bId} other={aId} onChange={(id) => onChange(aId, id)} />
          </div>
        </div>

        <div className="compare__cards">
          <MissionCard side={a} winner={a.badge === 'WINNER'} />
          <MissionCard side={b} winner={b.badge === 'WINNER'} />
        </div>

        <div className="compare__matrix" role="table" aria-label="Comparison matrix">
          <div className="matrix__row matrix__row--head" role="row">
            <span className="matrix__metric">METRIC</span>
            <span className="matrix__cell matrix__cell--head matrix__cell--accent">
              {a.mission.name.toUpperCase()} · {a.mission.site.toUpperCase()}
            </span>
            <span className="matrix__cell matrix__cell--head">
              {b.mission.name.toUpperCase()} · {b.mission.site.toUpperCase()}
            </span>
          </div>
          {rows.map((row, i) => (
            <MatrixRow key={row.label} row={row} tinted={i % 2 === 0} />
          ))}
        </div>

        <section className="compare__brief">
          <header>
            <span className="compare__brief-dot" />
            <h3>06 // PLAIN-LANGUAGE SCIENCE BRIEF</h3>
          </header>
          <p>{brief}</p>
          <footer>
            <span>{citations}</span>
            <span>
              SECURITY: UNCLASSIFIED // <em>NASA GSFC</em>
            </span>
          </footer>
        </section>
      </div>
    </div>
  )
}

function Picker({
  label,
  value,
  other,
  onChange,
}: {
  label: string
  value: string
  other: string
  onChange: (id: string) => void
}) {
  return (
    <label className="picker">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {missions.map((m) => (
          <option key={m.id} value={m.id} disabled={m.id === other}>
            {m.name} — {m.site}
          </option>
        ))}
      </select>
    </label>
  )
}

function MissionCard({ side, winner }: { side: CompareSide; winner: boolean }) {
  const { mission } = side
  return (
    <article className={`mission${winner ? ' mission--winner' : ''}`}>
      <div className="mission__top">
        <div>
          <p className="mission__eyebrow">{side.eyebrow}</p>
          <h2>{mission.name}</h2>
          <p className="mission__target">{side.target}</p>
        </div>
        <span className={`mission__badge${winner ? ' mission__badge--winner' : ''}`}>{side.badge}</span>
      </div>
      <div className="mission__score">
        <div>
          <strong>{mission.score}</strong>
          <span>/ 100</span>
          <em>VIABILITY INDEX</em>
        </div>
        <div className="track">
          <div
            className={`track__fill${winner ? ' track__fill--accent' : ' track__fill--white'}`}
            style={{ width: `${mission.score}%` }}
          />
        </div>
      </div>
    </article>
  )
}

function MatrixRow({ row, tinted }: { row: CompareRow; tinted: boolean }) {
  return (
    <div className={`matrix__row${tinted ? ' matrix__row--tint' : ''}`} role="row">
      <div className="matrix__metric">
        <span>{row.eyebrow}</span>
        <strong>{row.label}</strong>
      </div>
      {(['a', 'b'] as const).map((key) => {
        const cell = row[key]
        const won = row.winner === key
        return (
          <div className="matrix__cell" key={key}>
            <div className="matrix__value">
              <span className={won ? 'matrix__value--win' : undefined}>
                {cell.value} <em>{cell.note}</em>
              </span>
              {won && <span className="matrix__win">WIN</span>}
            </div>
            <div className="track track--thin">
              <div
                className={`track__fill${won ? ' track__fill--accent' : ' track__fill--dim'}`}
                style={{ width: `${cell.fill}%` }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
