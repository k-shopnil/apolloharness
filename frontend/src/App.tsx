import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { CompareView } from './components/CompareView'
import { FleetSidebar } from './components/FleetSidebar'
import { Header } from './components/Header'
import { MissionDrawer } from './components/MissionDrawer'
import { ProvenanceModal } from './components/ProvenanceModal'
import { SiteHud, type UIMode } from './components/SiteHud'
import { SiteView } from './components/SiteView'
import { TimelineScrubber } from './components/TimelineScrubber'
import { COMPACT_QUERY, useMediaQuery } from './hooks/useMediaQuery'
import {
  formatCoords,
  inGroup,
  isLocated,
  loadMissions,
  type LocatedMission,
  type MissionGroup,
  missionsFor,
  type Mission,
  type MissionFilter,
} from './data/missions'
import { sampleTrack } from './data/timeline'
import { loadTrackIndex, useTrack } from './data/tracks'

// Cesium is the bulk of the bundle; load it after the page shell has painted.
const MoonGlobe = lazy(() => import('./components/MoonGlobe').then((m) => ({ default: m.MoonGlobe })))

type Screen = 'fleet' | 'site' | 'compare'

/** Globe HUD text, derived from the selected mission and the catalog only. */
function hudFor(mission: Mission | null): { target: string; readout: string } {
  if (!mission) return { target: 'Lunar mission catalog', readout: '' }
  const coord = isLocated(mission) ? formatCoords(mission.lat, mission.lon) : 'No coordinate published'
  const kind = mission.coordinateType.replace(/_/g, ' ')
  return {
    target: mission.targetSite,
    readout: `${coord} · ${kind.charAt(0).toUpperCase()}${kind.slice(1)}`,
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
          Could not load the mission catalog ({loadError}).{' '}
          <button type="button" onClick={() => setAttempt((n) => n + 1)}>
            Retry
          </button>
        </div>
      </div>
    )
  }
  if (!missions) {
    return (
      <div className="app">
        <div className="globe globe--loading">Loading mission catalog…</div>
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
  const [group, setGroup] = useState<MissionGroup>('all')
  const [mode, setMode] = useState<UIMode>('simple')
  const [scrub, setScrub] = useState<{ id: string; hours: number }>({ id: '', hours: 0 })
  const [showProvenance, setShowProvenance] = useState(false)
  const [pair, setPair] = useState<{ a: string; b: string }>(() => ({ a: activeId0(missions), b: partnerFor(missions, activeId0(missions)) }))

  const compact = useMediaQuery(COMPACT_QUERY)
  const trackLookup = useTrack(activeId)
  const hours = scrub.id === activeId ? scrub.hours : 0
  const setHours = useCallback((h: number) => setScrub({ id: activeId, hours: h }), [activeId])
  const trackData = trackLookup.state === 'ready' ? trackLookup.data : null
  const activeMission = missions.find((m) => m.id === activeId)
  const sample = useMemo(() => (trackData ? sampleTrack(trackData.track, hours) : null), [trackData, hours])
  const scoped = useMemo(() => missions.filter((m) => inGroup(m, group)), [missions, group])
  const visible = useMemo(() => missionsFor(scoped, filter), [scoped, filter])
  const located = useMemo(() => missions.filter(isLocated), [missions])
  const getMission = (id: string) => missions.find((m) => m.id === id)!
  const highlightIds = useMemo(() => new Set(visible.map((m) => m.id)), [visible])
  const drawerMission = drawerOpen ? getMission(activeId) : null

  const changeFilter = (next: MissionFilter) => {
    setFilter(next)
    setDrawerOpen(false)
    setScreen('fleet')
    const list = missionsFor(scoped, next)
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
      <Header mode={mode} onModeChange={setMode} missions={scoped} filter={filter} onFilterChange={changeFilter} />
      <main className="app__main" data-screen={screen}>
        {screen === 'fleet' && (
          <>
            <Suspense fallback={<div className="globe globe--loading">Loading lunar surface…</div>}>
              <MoonGlobe
                missions={located}
                highlightIds={highlightIds}
                activeId={activeId}
                drawerOpen={drawerOpen}
                onSelect={selectMission}
                onCompare={() => openCompare()}
                compact={compact}
                hud={hudFor(missions.find((m) => m.id === activeId) ?? null)}
                sample={isLocated(activeMission!) ? sample : null}
              >
                {trackData && sample && activeMission && isLocated(activeMission) ? (
                  <>
                    <SiteHud mode={mode} mission={activeMission} data={trackData} sample={sample} />
                    <TimelineScrubber track={trackData.track} hours={hours} onChange={setHours} />
                  </>
                ) : (
                  <div className="hud hud--note">
                    {trackLookup.state === 'loading'
                      ? 'Loading track…'
                      : trackLookup.state === 'ready'
                        ? 'No coordinate published, so there is nothing to compute.'
                        : `Unavailable: ${trackLookup.reason}`}
                  </div>
                )}
              </MoonGlobe>
            </Suspense>
            <FleetSidebar filter={filter} missions={visible} group={group} onGroupChange={setGroup} activeId={activeId} onSelect={selectMission} />
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
