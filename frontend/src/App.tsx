import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { CompareView } from './components/CompareView'
import { FleetSidebar } from './components/FleetSidebar'
import { Header } from './components/Header'
import { MissionDrawer } from './components/MissionDrawer'
import { ProvenanceModal } from './components/ProvenanceModal'
import { SiteView } from './components/SiteView'
import { COMPACT_QUERY, useMediaQuery } from './hooks/useMediaQuery'
import {
  formatCoords,
  isLocated,
  loadMissions,
  type LocatedMission,
  missionsFor,
  type Mission,
  type MissionFilter,
} from './data/missions'
import { loadTrackIndex } from './data/tracks'

// Cesium is the bulk of the bundle; load it after the page shell has painted.
const MoonGlobe = lazy(() => import('./components/MoonGlobe').then((m) => ({ default: m.MoonGlobe })))

type Screen = 'fleet' | 'site' | 'compare'

const FILTER_NOTE: Record<MissionFilter, string> = {
  all: '',
  volatiles: ' // VOLATILE PAYLOAD FILTER',
  spectrometers: ' // SPECTROMETER PAYLOAD FILTER',
  rovers: ' // ROVER PAYLOAD FILTER',
}

/** Globe HUD text, derived from the selected mission and the catalog only. */
function hudFor(mission: Mission | null, filter: MissionFilter): { target: string; readout: string } {
  if (!mission) return { target: `LUNAR MISSION CATALOG${FILTER_NOTE[filter]}`, readout: '' }
  const coord = isLocated(mission) ? formatCoords(mission.lat, mission.lon) : 'NO COORDINATE PUBLISHED'
  return {
    target: `TARGET: ${mission.targetSite.toUpperCase()}${FILTER_NOTE[filter]}`,
    readout: `${coord}  |  ${mission.coordinateType.replace(/_/g, ' ').toUpperCase()}`,
  }
}

const DEFAULT_ACTIVE = 'clps-prime-1-im2'
const PREFERRED_PARTNERS = ['clps-to2-im-im1', 'anchor-apollo-17']

export default function App() {
  const [missions, setMissions] = useState<Mission[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [trackIds, setTrackIds] = useState<ReadonlySet<string>>(new Set())
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    loadMissions()
      .then((m) => !cancelled && (setMissions(m), setLoadError(null)))
      .catch((e: Error) => !cancelled && setLoadError(e.message))
    loadTrackIndex()
      .then((idx) => {
        if (!cancelled) setTrackIds(new Set([...idx.values()].filter((e) => e.status === 'complete').map((e) => e.mission_id)))
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [attempt])

  if (loadError) {
    return (
      <div className="app">
        <div className="globe globe--loading" role="alert">
          COULD NOT LOAD MISSION CATALOG ({loadError}).{' '}
          <button type="button" onClick={() => setAttempt((n) => n + 1)}>
            RETRY
          </button>
        </div>
      </div>
    )
  }
  if (!missions) {
    return (
      <div className="app">
        <div className="globe globe--loading">LOADING MISSION CATALOG…</div>
      </div>
    )
  }
  return <Workspace missions={missions} trackIds={trackIds} />
}

function Workspace({ missions, trackIds }: { missions: Mission[]; trackIds: ReadonlySet<string> }) {
  const [screen, setScreen] = useState<Screen>('fleet')
  const [filter, setFilter] = useState<MissionFilter>('all')
  const [activeId, setActiveId] = useState<string>(missions.find((m) => m.id === DEFAULT_ACTIVE)?.id ?? missions[0].id)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [showProvenance, setShowProvenance] = useState(false)
  const [pair, setPair] = useState<{ a: string; b: string }>(() => ({ a: activeId0(missions), b: partnerFor(missions, activeId0(missions)) }))

  const compact = useMediaQuery(COMPACT_QUERY)
  const visible = useMemo(() => missionsFor(missions, filter), [missions, filter])
  const located = useMemo(() => missions.filter(isLocated), [missions])
  const getMission = (id: string) => missions.find((m) => m.id === id)!
  const highlightIds = useMemo(() => new Set(visible.map((m) => m.id)), [visible])
  const drawerMission = drawerOpen ? getMission(activeId) : null

  const changeFilter = (next: MissionFilter) => {
    setFilter(next)
    setDrawerOpen(false)
    setScreen('fleet')
    const list = missionsFor(missions, next)
    if (list.length && !list.some((m) => m.id === activeId)) setActiveId(list[0].id)
  }

  // Selecting a pin or card flies the camera to the site and slides out the drawer.
  const selectMission = useCallback((id: string) => {
    setActiveId(id)
    setDrawerOpen(true)
  }, [])

  const closeDrawer = useCallback(() => setDrawerOpen(false), [])

  const openCompare = (fromId?: string) => {
    const a = fromId ?? activeId
    setPair({ a, b: partnerFor(missions, a) })
    setDrawerOpen(false)
    setScreen('compare')
  }

  const openInspector = (mission: Mission) => {
    setActiveId(mission.id)
    setScreen('site')
  }

  return (
    <div className="app">
      <Header missions={missions} filter={filter} onFilterChange={changeFilter} />
      <main className="app__main" data-screen={screen}>
        {screen === 'fleet' && (
          <>
            <Suspense fallback={<div className="globe globe--loading">LOADING LUNAR SURFACE…</div>}>
              <MoonGlobe
                missions={located}
                highlightIds={highlightIds}
                activeId={activeId}
                drawerOpen={drawerOpen}
                onSelect={selectMission}
                onCompare={() => openCompare()}
                compact={compact}
                hud={hudFor(missions.find((m) => m.id === activeId) ?? null, filter)}
              />
            </Suspense>
            <FleetSidebar filter={filter} missions={visible} activeId={activeId} onSelect={selectMission} />
            <MissionDrawer
              mission={drawerMission}
              onClose={closeDrawer}
              onCompare={(m) => openCompare(m.id)}
              onOpenProvenance={() => setShowProvenance(true)}
              onOpenInspector={drawerMission && isLocated(drawerMission) && trackIds.has(drawerMission.id) ? openInspector : undefined}
            />
          </>
        )}
        {screen === 'site' && isLocated(getMission(activeId)) && (
          <SiteView
            mission={getMission(activeId) as LocatedMission}
            onBack={() => {
              setDrawerOpen(true)
              setScreen('fleet')
            }}
            onCompare={() => openCompare(activeId)}
            onOpenProvenance={() => setShowProvenance(true)}
          />
        )}
        {screen === 'compare' && (
          <CompareView
            missions={missions}
            aId={pair.a}
            bId={pair.b}
            onChange={(a, b) => setPair({ a, b })}
            onBack={() => setScreen('fleet')}
          />
        )}
      </main>
      {showProvenance && <ProvenanceModal mission={getMission(activeId)} onClose={() => setShowProvenance(false)} />}
    </div>
  )
}

function activeId0(missions: Mission[]): string {
  return missions.find((m) => m.id === DEFAULT_ACTIVE)?.id ?? missions[0].id
}

/** Default comparison partner: a located mission other than `id`. */
function partnerFor(missions: Mission[], id: string): string {
  const pool = missions.filter((m) => isLocated(m) && m.id !== id)
  return (PREFERRED_PARTNERS.map((p) => pool.find((m) => m.id === p)).find(Boolean) ?? pool[0]).id
}
