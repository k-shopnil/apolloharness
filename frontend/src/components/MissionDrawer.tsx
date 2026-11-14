import { useEffect, type ReactNode } from 'react'
import { MissionDetails } from './MissionDetails'
import type { Mission } from '../data/missions'
import './MissionDrawer.css'

interface MissionDrawerProps {
  /** The mission to show; null slides the drawer out of view. */
  mission: Mission | null
  onClose: () => void
  onCompare: (mission: Mission) => void
  onOpenProvenance: () => void
  onOpenInspector?: (mission: Mission) => void
  /** Shown instead of the mission details when the drawer holds a custom point. */
  customPanel?: ReactNode
}

export function MissionDrawer({ mission, onClose, onCompare, onOpenProvenance, onOpenInspector, customPanel }: MissionDrawerProps) {
  const open = mission !== null

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  return (
    <aside className={`drawer${open ? ' drawer--open' : ''}`} aria-hidden={!open} aria-label="Mission detail">
      <div className="drawer__bar">
        <button type="button" className="drawer__close" onClick={onClose} tabIndex={open ? 0 : -1}>
          <svg
            viewBox="0 0 52 52"
            width="12"
            height="12"
            fill="currentColor"
            aria-hidden="true"
            focusable="false"
          >
            <path d="M38 52a2 2 0 0 1-1.41-.59l-24-24a2 2 0 0 1 0-2.82l24-24a2 2 0 0 1 2.82 0 2 2 0 0 1 0 2.82L16.83 26 39.41 48.59A2 2 0 0 1 38 52Z" />
          </svg>
          All missions
        </button>
      </div>
      <div className="drawer__scroll">
        {mission?.kind === 'custom' && customPanel}
        {mission && mission.kind !== 'custom' && (
          <MissionDetails
            key={mission.id}
            mission={mission}
            onCompare={() => onCompare(mission)}
            onOpenProvenance={onOpenProvenance}
            onOpenInspector={onOpenInspector ? () => onOpenInspector(mission) : undefined}
          />
        )}
      </div>
    </aside>
  )
}
