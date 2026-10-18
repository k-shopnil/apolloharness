import { lazy, Suspense, useCallback, useMemo, useState } from 'react'
import { CompareView } from './components/CompareView'
import { FleetSidebar } from './components/FleetSidebar'
import { Header } from './components/Header'
import { MissionDrawer } from './components/MissionDrawer'
import { ProvenanceModal } from './components/ProvenanceModal'
import { SiteView } from './components/SiteView'
import { COMPACT_QUERY, useMediaQuery } from './hooks/useMediaQuery'
import { getMission, missions, missionsFor, type Mission, type MissionFilter } from './data/missions'

// Cesium is the bulk of the bundle; load it after the page shell has painted.
const MoonGlobe = lazy(() => import('./components/MoonGlobe').then((m) => ({ default: m.MoonGlobe })))

type Screen = 'fleet' | 'site' | 'compare'

/** Missions that have a zoomed Site Inspector screen in the design. */
const INSPECTABLE = new Set(['im-2'])

const hudByFilter: Record<MissionFilter, { target: string; readout: string }> = {
  all: {
    target: 'TARGET: LUNAR SOUTH POLE',
    readout: 'LAT: 84.80°S  LON: 29.20°E  |  LOLA 20m DEM',
  },
  volatiles: {
    target: 'TARGET: LUNAR SOUTH POLE // VOLATILE PROSPECTING FILTER',
    readout: 'LAT: 84.80°S  LON: 29.20°E  |  LOLA 20m DEM  |  VOLATILE TRAPS ACTIVE',
  },
  spectrometers: {
    target: 'TARGET: LUNAR SOUTH POLE // SPECTROMETER PAYLOAD FILTER',
    readout: 'LAT: 84.80°S  LON: 29.20°E  |  LOLA 20m DEM  |  SPECTROMETER SITES ACTIVE',
  },
  rovers: {
    target: 'TARGET: LUNAR SOUTH POLE // ROVERS & SURFACE MOBILITY FILTER',
    readout: 'LAT: 85.00°S  LON: 31.60°W  |  LOLA 20m DEM  |  TRAVERSE TRAJECTORIES ACTIVE',
  },
}

/** Default comparison partner: the best-scoring other site. */
function bestAlternative(id: string): string {
  return missions
    .filter((m) => m.id !== id)
    .reduce((best, m) => (m.score > best.score ? m : best)).id
}

export default function App() {
  const [screen, setScreen] = useState<Screen>('fleet')
  const [filter, setFilter] = useState<MissionFilter>('all')
  const [activeId, setActiveId] = useState<string>('im-2')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [showProvenance, setShowProvenance] = useState(false)
  const [pair, setPair] = useState<{ a: string; b: string }>({ a: 'im-2', b: 'griffin-1' })

  const compact = useMediaQuery(COMPACT_QUERY)
  const visible = useMemo(() => missionsFor(filter), [filter])
  const highlightIds = useMemo(() => new Set(visible.map((m) => m.id)), [visible])
  const drawerMission = drawerOpen ? getMission(activeId) : null

  const changeFilter = (next: MissionFilter) => {
    setFilter(next)
    setDrawerOpen(false)
    setScreen('fleet')
    const list = missionsFor(next)
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
    setPair({ a, b: bestAlternative(a) })
    setDrawerOpen(false)
    setScreen('compare')
  }

  const openInspector = (mission: Mission) => {
    setActiveId(mission.id)
    setScreen('site')
  }

  return (
    <div className="app">
      <Header filter={filter} onFilterChange={changeFilter} />
      <main className="app__main" data-screen={screen}>
        {screen === 'fleet' && (
          <>
            <Suspense fallback={<div className="globe globe--loading">LOADING LUNAR SURFACE…</div>}>
              <MoonGlobe
                missions={missions}
                highlightIds={highlightIds}
                activeId={activeId}
                drawerOpen={drawerOpen}
                onSelect={selectMission}
                onCompare={() => openCompare()}
                compact={compact}
                hud={hudByFilter[filter]}
              />
            </Suspense>
            <FleetSidebar filter={filter} missions={visible} activeId={activeId} onSelect={selectMission} />
            <MissionDrawer
              mission={drawerMission}
              onClose={closeDrawer}
              onCompare={(m) => openCompare(m.id)}
              onOpenProvenance={() => setShowProvenance(true)}
              onOpenInspector={drawerMission && INSPECTABLE.has(drawerMission.id) ? openInspector : undefined}
            />
          </>
        )}
        {screen === 'site' && (
          <SiteView
            mission={getMission(activeId)}
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
            aId={pair.a}
            bId={pair.b}
            onChange={(a, b) => setPair({ a, b })}
            onBack={() => setScreen('fleet')}
          />
        )}
      </main>
      {showProvenance && <ProvenanceModal onClose={() => setShowProvenance(false)} />}
    </div>
  )
}
