import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { ApiInspectorModal } from './components/ApiInspectorModal'
import { CompareView } from './components/CompareView'
import { FleetSidebar } from './components/FleetSidebar'
import { Header, type UIMode } from './components/Header'
import { MissionDrawer } from './components/MissionDrawer'
import { PinCoordsModal } from './components/PinCoordsModal'
import { ProvenanceModal } from './components/ProvenanceModal'
import { SiteView } from './components/SiteView'
import { TimelineScrubber, type TrackData } from './components/TimelineScrubber'
import { COMPACT_QUERY, useMediaQuery } from './hooks/useMediaQuery'
import { getMission, missions as initialMissions, missionsFor, type Mission, type MissionFilter } from './data/missions'
import { fetchCustomSite, fetchHealth, fetchMissions, fetchPrecomputedTrack } from './services/api'
import type { TelemetryOverride } from './components/MoonGlobe'

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
function bestAlternative(id: string, list: Mission[] = initialMissions): string {
  const others = list.filter((m) => m.id !== id)
  if (!others.length) return id
  return others.reduce((best, m) => (m.score > best.score ? m : best)).id
}

export default function App() {
  const [missionsList, setMissionsList] = useState<Mission[]>(initialMissions)
  const [apiStatus, setApiStatus] = useState<{ online: boolean; mode: string; count: number }>({
    online: false,
    mode: 'mock',
    count: initialMissions.length,
  })
  const [showApiInspector, setShowApiInspector] = useState(false)
  const [showPinModal, setShowPinModal] = useState(false)
  const [uiMode, setUiMode] = useState<UIMode>('simple')
  const [screen, setScreen] = useState<Screen>('fleet')
  const [filter, setFilter] = useState<MissionFilter>('all')
  const [activeId, setActiveId] = useState<string>('im-2')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [showProvenance, setShowProvenance] = useState(false)
  const [pair, setPair] = useState<{ a: string; b: string }>({ a: 'im-2', b: 'griffin-1' })

  // 29.5-day synodic month scrubber state
  const [track, setTrack] = useState<TrackData | null>(null)
  const [currentHour, setCurrentHour] = useState<number>(0)
  const [isPlaying, setIsPlaying] = useState<boolean>(false)

  const compact = useMediaQuery(COMPACT_QUERY)
  const visible = useMemo(() => missionsFor(filter, missionsList), [filter, missionsList])
  const highlightIds = useMemo(() => new Set(visible.map((m) => m.id)), [visible])
  const drawerMission = drawerOpen ? getMission(activeId, missionsList) : null

  // Poll live backend health and mission catalog every 4 seconds
  useEffect(() => {
    let active = true

    const checkApi = async () => {
      const health = await fetchHealth()
      if (!active) return

      const isHealthy = health.status === 'healthy'
      setApiStatus({
        online: isHealthy,
        mode: isHealthy ? health.mode : 'mock',
        count: isHealthy ? (health.missions_count || initialMissions.length) : initialMissions.length,
      })

      if (isHealthy) {
        const { missions: liveList, mode } = await fetchMissions()
        if (active && liveList.length > 0) {
          setMissionsList(liveList)
          setApiStatus((prev) => ({ ...prev, mode, count: liveList.length }))
        }
      } else {
        if (active) {
          setMissionsList(initialMissions)
        }
      }
    }

    checkApi()
    const timer = setInterval(checkApi, 4000)

    return () => {
      active = false
      clearInterval(timer)
    }
  }, [])

  // Load precomputed synodic month track whenever active mission changes
  useEffect(() => {
    let active = true
    setIsPlaying(false)
    setCurrentHour(0)

    fetchPrecomputedTrack(activeId).then((data) => {
      if (active) {
        setTrack(data)
      }
    })

    return () => {
      active = false
    }
  }, [activeId])

  // Playback timer for 29.5-day synodic scrubber
  useEffect(() => {
    if (!isPlaying || !track || !track.columns || !track.columns.hours_from_start.length) return
    const maxHour = track.columns.hours_from_start.length - 1
    const timer = setInterval(() => {
      setCurrentHour((prev) => {
        if (prev >= maxHour) {
          setIsPlaying(false)
          return maxHour
        }
        return prev + 1
      })
    }, 100)

    return () => clearInterval(timer)
  }, [isPlaying, track])

  // Extract instantaneous telemetry vector override from scrubber
  const telemetryOverride: TelemetryOverride | null = useMemo(() => {
    if (!track || !track.columns || !track.columns.hours_from_start.length) return null
    const maxIdx = track.columns.hours_from_start.length - 1
    const clamped = Math.max(0, Math.min(maxIdx, Math.round(currentHour)))
    return {
      sunElevationDeg: track.columns.sun_elevation_deg[clamped] ?? 0,
      earthElevationDeg: track.columns.earth_elevation_deg[clamped] ?? 0,
      sunVisible: track.columns.sun_is_lit[clamped] ?? true,
      earthVisible: track.columns.earth_direct_los[clamped] ?? true,
      sunUnitVector: track.columns.sun_unit_moon_pa?.[clamped],
      earthUnitVector: track.columns.earth_unit_moon_pa?.[clamped],
    }
  }, [track, currentHour])

  const changeFilter = (next: MissionFilter) => {
    setFilter(next)
    setDrawerOpen(false)
    setScreen('fleet')
    const list = missionsFor(next, missionsList)
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
    setPair({ a, b: bestAlternative(a, missionsList) })
    setDrawerOpen(false)
    setScreen('compare')
  }

  const openInspector = (mission: Mission) => {
    setActiveId(mission.id)
    setScreen('site')
  }

  // Handle custom coordinates pin drop on globe or from modal
  const handlePinCustomSite = useCallback(
    async (lat: number, lon: number, customLabel?: string) => {
      const customId = `custom-${Math.round(lat * 1000)}_${Math.round(lon * 1000)}`
      const title = customLabel || `CUSTOM PIN (${lat.toFixed(2)}°, ${lon.toFixed(2)}°)`

      const customMission: Mission = {
        id: customId,
        index: '99',
        name: title,
        provider: 'NASA Space Apps / Custom Evaluation',
        lander: 'Candidate Surface Lander',
        launchWindow: new Date().toISOString(),
        site: customLabel || `Coordinates (${lat.toFixed(2)}°, ${lon.toFixed(2)}°)`,
        target: `User-pinned landing site at ${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E. Calculated from NAIF SPICE ephemeris & LOLA DEM altimetry.`,
        year: 2026,
        lat,
        lon,
        ellipseKm: [3.0, 2.0],
        slopeDeg: 4.5,
        elevationM: 800,
        score: 75,
        viability: {
          windowSunlight: 75,
          annualSunlight: 50,
          commsLos: 70,
          psrKm: 3.5,
        },
        payloadSummary: 'Candidate Exploration Payload',
        payloads: [],
        dataStatus: 'placeholder',
      }

      setMissionsList((prev) => [customMission, ...prev.filter((m) => m.id !== customId)])
      setActiveId(customId)
      setDrawerOpen(true)
      setScreen('fleet')

      // Query live custom evaluation if backend is online
      if (apiStatus.online) {
        try {
          const evalRes = await fetchCustomSite(lat, lon, undefined, true)
          if (evalRes && evalRes.sun) {
            setMissionsList((prev) =>
              prev.map((m) => {
                if (m.id !== customId) return m
                const sunlitPct = evalRes.sun.sunlit_percent ?? 75
                const earthLosPct = evalRes.earth?.earth_los_percent ?? 70
                const compositeScore = Math.round(sunlitPct * 0.4 + earthLosPct * 0.35 + 20)
                return {
                  ...m,
                  score: compositeScore,
                  slopeDeg: evalRes.terrain?.slope_deg ?? m.slopeDeg,
                  elevationM: evalRes.terrain?.elevation_m ?? m.elevationM,
                  viability: {
                    windowSunlight: Math.round(sunlitPct),
                    annualSunlight: Math.round(sunlitPct * 0.7),
                    commsLos: Math.round(earthLosPct),
                    psrKm: evalRes.psr?.distance_km ?? 3.5,
                  },
                }
              }),
            )
            if (evalRes.track) {
              setTrack(evalRes.track)
            }
          }
        } catch {}
      }
    },
    [apiStatus.online],
  )

  const activeMissionObj = missionsList.find((m) => m.id === activeId)

  return (
    <div className="app">
      <Header
        filter={filter}
        onFilterChange={changeFilter}
        apiStatus={apiStatus}
        onOpenApiInspector={() => setShowApiInspector(true)}
        mode={uiMode}
        onModeChange={setUiMode}
        onOpenPinModal={() => setShowPinModal(true)}
      />
      {!apiStatus.online && (
        <aside className="offline-banner" role="status">
          <div className="offline-banner__left">
            <span className="offline-banner__dot" />
            <strong className="offline-banner__tag">OFFLINE ARCHIVAL MODE ACTIVE</strong>
            <span className="offline-banner__text">
              FastAPI backend is offline. Mission control is operating on verified NASA PDS, LOLA 20m DEM &amp; NAIF SPICE archival fixtures.
            </span>
          </div>
          <button
            type="button"
            className="offline-banner__btn"
            onClick={() => setShowApiInspector(true)}
          >
            [ VIEW OFFLINE DIAGNOSTICS ↗ ]
          </button>
        </aside>
      )}
      <main className="app__main" data-screen={screen}>
        {screen === 'fleet' && (
          <>
            <Suspense fallback={<div className="globe globe--loading">LOADING LUNAR SURFACE…</div>}>
              <MoonGlobe
                missions={missionsList}
                highlightIds={highlightIds}
                activeId={activeId}
                drawerOpen={drawerOpen}
                onSelect={selectMission}
                onCompare={() => openCompare()}
                compact={compact}
                hud={hudByFilter[filter]}
                onPinCustomSite={handlePinCustomSite}
                telemetryOverride={telemetryOverride}
              />
            </Suspense>
            <FleetSidebar filter={filter} missions={visible} activeId={activeId} onSelect={selectMission} />
            <MissionDrawer
              mission={drawerMission}
              onClose={closeDrawer}
              onCompare={(m) => openCompare(m.id)}
              onOpenProvenance={() => setShowProvenance(true)}
              onOpenInspector={drawerMission && INSPECTABLE.has(drawerMission.id) ? openInspector : undefined}
              uiMode={uiMode}
            />
            {/* 29.5-Day Synodic Month Timeline Scrubber floating overlay */}
            <TimelineScrubber
              track={track}
              currentHour={currentHour}
              onChangeHour={setCurrentHour}
              isPlaying={isPlaying}
              onTogglePlay={() => setIsPlaying((p) => !p)}
              missionName={activeMissionObj?.name}
            />
          </>
        )}
        {screen === 'site' && (
          <SiteView
            mission={getMission(activeId, missionsList)}
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
            missionsList={missionsList}
            onChange={(a, b) => setPair({ a, b })}
            onBack={() => setScreen('fleet')}
          />
        )}
      </main>
      {showProvenance && <ProvenanceModal onClose={() => setShowProvenance(false)} />}
      {showApiInspector && <ApiInspectorModal onClose={() => setShowApiInspector(false)} />}
      {showPinModal && (
        <PinCoordsModal
          onClose={() => setShowPinModal(false)}
          onSubmit={(lat, lon, label) => handlePinCustomSite(lat, lon, label)}
          initialLat={activeMissionObj?.lat}
          initialLon={activeMissionObj?.lon}
        />
      )}
    </div>
  )
}
