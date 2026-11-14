import { useEffect } from 'react'
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
}

export function MissionDrawer({ mission, onClose, onCompare, onOpenProvenance, onOpenInspector }: MissionDrawerProps) {
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
          ← All missions
        </button>
      </div>
      <div className="drawer__scroll">
        {mission && (
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
