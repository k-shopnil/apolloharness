import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  ArcType,
  Cartesian2,
  CallbackProperty,
  Cartesian3,
  Color,
  Credit,
  Ellipsoid,
  GeographicTilingScheme,
  ImageryLayer,
  LabelStyle,
  Math as CesiumMath,
  PolylineDashMaterialProperty,
  PolylineGlowMaterialProperty,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  Transforms,
  UrlTemplateImageryProvider,
  Viewer,
  VerticalOrigin,
  HorizontalOrigin,
  Matrix4,
  defined,
} from 'cesium'
import 'cesium/Build/Cesium/Widgets/widgets.css'
import type { LocatedMission } from '../data/missions'
import { COMPACT_QUERY } from '../hooks/useMediaQuery'
import { ephemerisFrom, siteTelemetry } from '../data/ephemeris'
import type { TrackSample } from '../data/timeline'
import { SiteTelemetryCard } from './SiteTelemetryCard'
import './MoonGlobe.css'

// Cesium defaults to WGS84; the whole scene must use the lunar reference sphere.
Ellipsoid.default = Ellipsoid.MOON

// NASA Moon Trek: LRO WAC global mosaic (equirectangular).
const WAC_TILES =
  'https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/default/default028mm/{z}/{y}/{x}.jpg'

// Coarse levels (0-3) ship in public/tiles via `npm run fetch-tiles`, so the globe still
// renders offline. Finer levels stream from NASA and are cached by public/sw.js.
const LOCAL_TILES = '/tiles/{z}/{y}/{x}.jpg'
const LOCAL_MAX_LEVEL = 3
const REMOTE_MAX_LEVEL = 7
const CREDIT = 'NASA/GSFC/ASU · LRO WAC · Moon Trek'

function tileProvider(url: string, minimumLevel: number, maximumLevel: number) {
  return new UrlTemplateImageryProvider({
    url,
    tilingScheme: new GeographicTilingScheme({ ellipsoid: Ellipsoid.MOON }),
    ellipsoid: Ellipsoid.MOON,
    minimumLevel,
    maximumLevel,
    credit: new Credit(CREDIT),
  })
}

// Cesium rasterises label text to a bitmap at its font size. Drawing at LABEL_SS x and
// scaling back down keeps small HUD text crisp on high-DPI screens.
const LABEL_SS = Math.max(2, Math.ceil(window.devicePixelRatio || 1))
const LABEL_SCALE = 1 / LABEL_SS

const VIEW_HEIGHT = 4_200_000
const ACCENT = Color.fromCssColorString('#ff4d00')
const GRATICULE: { lat: number; label: string }[] = [
  { lat: -80, label: '80°S' },
  { lat: -60, label: '60°S' },
  { lat: -30, label: '30°S' },
]

interface MoonGlobeProps {
  /** Every mission; the globe dims those outside `highlightIds`. */
  missions: LocatedMission[]
  highlightIds: ReadonlySet<string>
  activeId: string | null
  /** When true the camera is parked over the active site with its landing ellipse drawn. */
  drawerOpen: boolean
  onSelect: (id: string) => void
  onCompare: () => void
  /** Phone layout: smaller resolution, fewer labels, bigger tap targets. */
  compact: boolean
  hud: { target: string; readout: string }
  /** Track values at the scrubber time for the active site; null when it has no track. */
  sample: TrackSample | null
  /** HUD panels and scrubber docked over the bottom of the globe. */
  children?: ReactNode
}

/** Pole view; pulled back on portrait screens so the whole Moon still fits the width. */
function poleView(aspect: number) {
  const pullBack = aspect < 1 ? Math.max(1, 0.62 / aspect) : 1
  return {
    destination: Cartesian3.fromDegrees(0, -90, VIEW_HEIGHT * pullBack),
    orientation: { heading: 0, pitch: CesiumMath.toRadians(-90), roll: 0 },
  }
}

function containerAspect(viewer: Viewer): number {
  const { clientWidth, clientHeight } = viewer.canvas
  return clientHeight ? clientWidth / clientHeight : 1
}

function flyToOverview(viewer: Viewer) {
  viewer.camera.flyTo({ ...poleView(containerAspect(viewer)), duration: 1.8 })
}

const SITE_VIEW_HEIGHT = 18_000

function flyToSite(viewer: Viewer, mission: LocatedMission) {
  viewer.camera.flyTo({
    destination: Cartesian3.fromDegrees(mission.lon, mission.lat, SITE_VIEW_HEIGHT),
    orientation: { heading: 0, pitch: CesiumMath.toRadians(-90), roll: 0 },
    duration: 2.2,
  })
}

/** 0..1 sawtooth, ~1.8s period, shared clock so beacons stay in step. */
function pulsePhase(offset: number): number {
  return ((performance.now() / 1800 + offset) % 1 + 1) % 1
}

const sprites = new Map<string, HTMLCanvasElement>()

/** Soft radial glow with a bright core, drawn once per colour. */
function glowSprite(css: string, ring = false): HTMLCanvasElement {
  const key = `${css}:${ring}`
  const cached = sprites.get(key)
  if (cached) return cached

  const size = 128
  const c = document.createElement('canvas')
  c.width = c.height = size
  const g = c.getContext('2d')!
  const mid = size / 2

  if (ring) {
    g.strokeStyle = css
    g.lineWidth = 3
    g.beginPath()
    g.arc(mid, mid, mid - 6, 0, Math.PI * 2)
    g.stroke()
  } else {
    const grad = g.createRadialGradient(mid, mid, 0, mid, mid, mid)
    grad.addColorStop(0, '#ffffff')
    grad.addColorStop(0.12, css)
    grad.addColorStop(0.3, css + '99')
    grad.addColorStop(1, css + '00')
    g.fillStyle = grad
    g.fillRect(0, 0, size, size)
  }
  sprites.set(key, c)
  return c
}

/** Earth / Sun billboards. Earth is a shaded blue marble, the Sun a hot white-yellow disc. */
function bodySprite(kind: 'earth' | 'sun'): HTMLCanvasElement {
  const key = `body:${kind}`
  const cached = sprites.get(key)
  if (cached) return cached
  const size = 128
  const c = document.createElement('canvas')
  c.width = c.height = size
  const g = c.getContext('2d')!
  const mid = size / 2
  if (kind === 'earth') {
    const halo = g.createRadialGradient(mid, mid, 30, mid, mid, mid)
    halo.addColorStop(0, '#4aa3ff55')
    halo.addColorStop(1, '#4aa3ff00')
    g.fillStyle = halo
    g.fillRect(0, 0, size, size)
    const body = g.createRadialGradient(mid - 12, mid - 12, 4, mid, mid, 32)
    body.addColorStop(0, '#9fd0ff')
    body.addColorStop(0.55, '#2a6fd6')
    body.addColorStop(1, '#0a2a66')
    g.fillStyle = body
    g.beginPath()
    g.arc(mid, mid, 30, 0, Math.PI * 2)
    g.fill()
    g.fillStyle = '#3f9b5a99' // a hint of landmass
    g.beginPath()
    g.ellipse(mid - 8, mid - 2, 11, 7, 0.5, 0, Math.PI * 2)
    g.ellipse(mid + 12, mid + 10, 7, 5, -0.4, 0, Math.PI * 2)
    g.fill()
  } else {
    const grad = g.createRadialGradient(mid, mid, 0, mid, mid, mid)
    grad.addColorStop(0, '#ffffff')
    grad.addColorStop(0.18, '#fff3b0')
    grad.addColorStop(0.4, '#ffb52e88')
    grad.addColorStop(1, '#ffb52e00')
    g.fillStyle = grad
    g.fillRect(0, 0, size, size)
  }
  sprites.set(key, c)
  return c
}

/** Earth/Sun are drawn at a compressed distance (real: 384,400 km) so they sit just off the limb. */
const BODY_DISTANCE = Ellipsoid.MOON.maximumRadius * 1.6
const BEAM_CYAN = Color.fromCssColorString('#00cfff')
const BEAM_RED = Color.fromCssColorString('#ff3b30')
const SOLAR_AMBER = Color.fromCssColorString('#ffb52e')

/** Distance in px between the site pin and the telemetry card; the CSS leader line spans it. */
const CARD_GAP = 64

/** Point on the compressed celestial sphere along a selenographic direction. */
function bodyPosition(d: { lat: number; lon: number }): Cartesian3 {
  const unit = Cartesian3.normalize(Cartesian3.fromDegrees(d.lon, d.lat, 0), new Cartesian3())
  return Cartesian3.multiplyByScalar(unit, BODY_DISTANCE, new Cartesian3())
}

/** Ring of `radiusM` metres around a surface point, projected onto the lunar sphere. */
function ringPositions(lat: number, lon: number, radiusM: number, ratio = 0.6): Cartesian3[] {
  const center = Cartesian3.fromDegrees(lon, lat, 0)
  const frame = Transforms.eastNorthUpToFixedFrame(center)
  const out: Cartesian3[] = []
  for (let i = 0; i <= 64; i++) {
    const a = (i / 64) * Math.PI * 2
    const local = new Cartesian3(Math.cos(a) * radiusM, Math.sin(a) * radiusM * ratio, 0)
    const world = Matrix4.multiplyByPoint(frame, local, new Cartesian3())
    out.push(Ellipsoid.MOON.scaleToGeodeticSurface(world, new Cartesian3()) ?? world)
  }
  return out
}

export function MoonGlobe({
  missions,
  highlightIds,
  activeId,
  drawerOpen,
  onSelect,
  onCompare,
  compact,
  hud,
  sample,
  children,
}: MoonGlobeProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const viewerRef = useRef<Viewer | null>(null)
  const selectRef = useRef(onSelect)
  selectRef.current = onSelect
  const mounted = useRef(false)
  const cardRef = useRef<HTMLDivElement>(null)
  const [layers, setLayers] = useState({ beam: true, solar: true })

  const eph = useMemo(() => ephemerisFrom(sample), [sample])
  const activeMission = missions.find((m) => m.id === activeId) ?? null
  const telemetry = useMemo(
    () => (activeMission && sample ? siteTelemetry(activeMission, sample) : null),
    [activeMission, sample],
  )

  // Create the viewer once.
  useEffect(() => {
    if (!containerRef.current) return

    const startsCompact = window.matchMedia(COMPACT_QUERY).matches
    const viewer = new Viewer(containerRef.current, {
      baseLayer: new ImageryLayer(tileProvider(LOCAL_TILES, 0, LOCAL_MAX_LEVEL)),
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      animation: false,
      timeline: false,
      fullscreenButton: false,
      infoBox: false,
      selectionIndicator: false,
      skyAtmosphere: false,
      skyBox: false,
      requestRenderMode: false,
    })

    // Detail layer: only requested past the local levels; failures are non-fatal when offline.
    const remote = tileProvider(WAC_TILES, LOCAL_MAX_LEVEL + 1, startsCompact ? REMOTE_MAX_LEVEL - 1 : REMOTE_MAX_LEVEL)
    remote.errorEvent.addEventListener((error) => {
      error.retry = false
    })
    viewer.imageryLayers.addImageryProvider(remote)

    if (startsCompact) {
      // Cap the render resolution: phone GPUs struggle at full device pixel ratio.
      viewer.useBrowserRecommendedResolution = false
      viewer.resolutionScale = Math.min(window.devicePixelRatio || 1, 1.5)
    }

    const { scene } = viewer
    scene.backgroundColor = Color.BLACK
    scene.globe.baseColor = Color.fromCssColorString('#0a0a0a')
    scene.globe.showGroundAtmosphere = false
    scene.globe.enableLighting = false
    if (scene.sun) scene.sun.show = false
    if (scene.moon) scene.moon.show = false
    scene.screenSpaceCameraController.minimumZoomDistance = 1_500
    scene.screenSpaceCameraController.maximumZoomDistance = 12_000_000

    viewer.camera.setView(poleView(containerAspect(viewer)))

    const handler = new ScreenSpaceEventHandler(scene.canvas)
    handler.setInputAction((click: { position: Cartesian2 }) => {
      const picked = scene.pick(click.position)
      const id = defined(picked) ? picked.id?.id : undefined
      if (typeof id === 'string' && /^(mission|pulse):/.test(id)) selectRef.current(id.slice(id.indexOf(':') + 1))
    }, ScreenSpaceEventType.LEFT_CLICK)

    viewerRef.current = viewer
    return () => {
      handler.destroy()
      viewer.destroy()
      viewerRef.current = null
    }
  }, [])

  // Graticule (static).
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer) return
    GRATICULE.forEach(({ lat, label }, i) => {
      const positions = Array.from({ length: 121 }, (_, k) => Cartesian3.fromDegrees(-180 + k * 3, lat, 1000))
      viewer.entities.add({
        id: `grid:${lat}`,
        polyline: {
          positions,
          width: 1,
          material:
            i === 0
              ? new PolylineDashMaterialProperty({ color: Color.WHITE.withAlpha(0.35), dashLength: 12 })
              : Color.WHITE.withAlpha(0.12),
        },
      })
      viewer.entities.add({
        id: `gridlabel:${lat}`,
        position: Cartesian3.fromDegrees(95, lat, 1000),
        label: {
          text: label,
          font: `${10 * LABEL_SS}px JetBrains Mono, monospace`,
          scale: LABEL_SCALE,
          fillColor: Color.WHITE.withAlpha(0.35),
          style: LabelStyle.FILL,
        },
      })
    })
    return () => {
      if (viewer.isDestroyed()) return
      GRATICULE.forEach(({ lat }) => {
        viewer.entities.removeById(`grid:${lat}`)
        viewer.entities.removeById(`gridlabel:${lat}`)
      })
    }
  }, [])

  // Beacon pins. Missions outside the filter are dimmed; the active one is orange.
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer) return
    const ids: string[] = []

    missions.forEach((m, i) => {
      const lit = highlightIds.has(m.id)
      const active = m.id === activeId
      const position = Cartesian3.fromDegrees(m.lon, m.lat, 1000)
      const tint = active ? '#ff4d00' : '#ffffff'
      const phaseOffset = (i * 0.37) % 1

      if (lit) {
        // Expanding ring that fades out, looping: the beacon pulse.
        const pulseId = `pulse:${m.id}`
        ids.push(pulseId)
        viewer.entities.add({
          id: pulseId,
          position,
          billboard: {
            image: glowSprite(tint, true),
            scale: new CallbackProperty(() => 0.18 + 0.42 * pulsePhase(phaseOffset), false),
            color: new CallbackProperty(
              () => Color.WHITE.withAlpha((1 - pulsePhase(phaseOffset)) * (active ? 0.9 : 0.55)),
              false,
            ),
          },
        })
      }

      const id = `mission:${m.id}`
      ids.push(id)
      viewer.entities.add({
        id,
        position,
        billboard: {
          image: glowSprite(tint),
          scale: (active ? 0.42 : lit ? 0.3 : 0.16) * (compact ? 1.35 : 1),
          color: Color.WHITE.withAlpha(lit ? 1 : 0.35),
        },
        label: {
          show: lit && (!compact || active),
          text: `${m.name}\n${m.targetSite}${m.isLandingFix ? '' : '\n(target / reference)'}`,
          font: `${active ? 'bold ' : ''}${11 * LABEL_SS}px JetBrains Mono, monospace`,
          scale: LABEL_SCALE,
          fillColor: active ? ACCENT : Color.fromCssColorString('#aaaaaa'),
          style: LabelStyle.FILL,
          showBackground: true,
          backgroundColor: Color.BLACK.withAlpha(0.7),
          backgroundPadding: new Cartesian2(6 * LABEL_SS, 4 * LABEL_SS),
          pixelOffset: new Cartesian2(14, -4),
          horizontalOrigin: HorizontalOrigin.LEFT,
          verticalOrigin: VerticalOrigin.CENTER,
        },
      })
    })

    const active = missions.find((m) => m.id === activeId)
    if (active && highlightIds.has(active.id)) {
      if (drawerOpen && active.ellipseMajorKm !== null && active.ellipseMinorKm !== null) {
        // Only drawn when the landing ellipse is published; never invented.
        // Semi-transparent landing ellipse draped on the surface around the site.
        ids.push('ellipse:active')
        viewer.entities.add({
          id: 'ellipse:active',
          position: Cartesian3.fromDegrees(active.lon, active.lat, 0),
          ellipse: {
            semiMajorAxis: active.ellipseMajorKm * 500,
            semiMinorAxis: active.ellipseMinorKm * 500,
            material: ACCENT.withAlpha(0.22),
            outline: true,
            outlineColor: ACCENT,
            height: 0,
          },
        })
      } else {
        ids.push('ring:active')
        viewer.entities.add({
          id: 'ring:active',
          polyline: {
            positions: ringPositions(active.lat, active.lon, 90_000),
            width: 1.5,
            material: new PolylineDashMaterialProperty({ color: ACCENT, dashLength: 10 }),
          },
        })
      }
    }

    return () => {
      if (viewer.isDestroyed()) return
      ids.forEach((id) => viewer.entities.removeById(id))
    }
  }, [missions, highlightIds, activeId, drawerOpen, compact])

  // Earth (always) and Sun (Solar Vectors layer) placed along the sub-Earth / sub-solar directions.
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || !eph) return
    viewer.entities.add({
      id: 'body:earth',
      position: bodyPosition(eph.subEarth),
      billboard: { image: bodySprite('earth'), scale: compact ? 0.55 : 0.7 },
      label: {
        text: 'EARTH',
        font: `${10 * LABEL_SS}px JetBrains Mono, monospace`,
        scale: LABEL_SCALE,
        fillColor: Color.fromCssColorString('#7db8ff'),
        style: LabelStyle.FILL,
        pixelOffset: new Cartesian2(0, 34),
      },
    })
    if (layers.solar) {
      viewer.entities.add({
        id: 'body:sun',
        position: bodyPosition(eph.subSolar),
        billboard: { image: bodySprite('sun'), scale: compact ? 0.55 : 0.75 },
        label: {
          text: 'SUN',
          font: `${10 * LABEL_SS}px JetBrains Mono, monospace`,
          scale: LABEL_SCALE,
          fillColor: SOLAR_AMBER,
          style: LabelStyle.FILL,
          pixelOffset: new Cartesian2(0, 34),
        },
      })
    }
    return () => {
      if (viewer.isDestroyed()) return
      viewer.entities.removeById('body:earth')
      viewer.entities.removeById('body:sun')
    }
  }, [eph, layers.solar, compact])

  // DTE line-of-sight beam (glowing cyan when clear, dashed red when occulted) and the solar vector.
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || !eph || !activeMission || !telemetry || !highlightIds.has(activeMission.id)) return
    const from = Cartesian3.fromDegrees(activeMission.lon, activeMission.lat, 1000)
    const ids: string[] = []

    if (layers.beam) {
      const dashed = new PolylineDashMaterialProperty({ color: BEAM_RED, dashLength: 14 })
      ids.push('beam:dte')
      viewer.entities.add({
        id: 'beam:dte',
        polyline: {
          positions: [from, bodyPosition(eph.subEarth)],
          arcType: ArcType.NONE,
          width: telemetry.losActive ? 6 : 2,
          material: telemetry.losActive
            ? new PolylineGlowMaterialProperty({ glowPower: 0.3, color: BEAM_CYAN })
            : dashed,
          // When the Moon blocks the line, still show it (dashed red) through the globe.
          depthFailMaterial: telemetry.losActive ? undefined : dashed,
        },
      })
    }

    if (layers.solar) {
      const sun = bodyPosition(eph.subSolar)
      const dir = Cartesian3.normalize(Cartesian3.subtract(sun, from, new Cartesian3()), new Cartesian3())
      // Short segment toward the Sun, not the full distance.
      const tip = Cartesian3.add(from, Cartesian3.multiplyByScalar(dir, BODY_DISTANCE * 0.45, new Cartesian3()), new Cartesian3())
      ids.push('vec:solar')
      viewer.entities.add({
        id: 'vec:solar',
        polyline: {
          positions: [from, tip],
          arcType: ArcType.NONE,
          width: 2,
          material: new PolylineDashMaterialProperty({
            color: SOLAR_AMBER.withAlpha(telemetry.power === 'NO SUN' ? 0.4 : 0.95),
            dashLength: 10,
          }),
        },
      })
    }

    return () => {
      if (viewer.isDestroyed()) return
      ids.forEach((id) => viewer.entities.removeById(id))
    }
  }, [activeMission, telemetry, highlightIds, layers, eph])

  // Keep the telemetry card pinned above the active site, every frame.
  useEffect(() => {
    const viewer = viewerRef.current
    const card = cardRef.current
    if (!viewer || !card || !activeMission || !highlightIds.has(activeMission.id)) return
    const anchor = Cartesian3.fromDegrees(activeMission.lon, activeMission.lat, 1000)
    const scratch = new Cartesian2()
    const update = () => {
      const p = viewer.scene.cartesianToCanvasCoordinates(anchor, scratch)
      if (!p) {
        card.style.visibility = 'hidden'
        return
      }
      card.style.visibility = 'visible'
      // Sit above the pin; flip below it when there isn't room before the top edge.
      const flip = p.y - CARD_GAP - card.offsetHeight < 8
      card.dataset.flip = flip ? 'down' : 'up'
      card.style.transform = flip
        ? `translate(${Math.round(p.x)}px, ${Math.round(p.y)}px) translate(-50%, 0) translateY(${CARD_GAP}px)`
        : `translate(${Math.round(p.x)}px, ${Math.round(p.y)}px) translate(-50%, -100%) translateY(-${CARD_GAP}px)`
    }
    const remove = viewer.scene.preRender.addEventListener(update)
    update()
    return () => {
      remove()
      card.style.visibility = 'hidden'
    }
  }, [activeMission, highlightIds, telemetry])

  // Camera: park over the site while the drawer is open, otherwise return to the pole view.
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer) return
    if (!mounted.current) {
      mounted.current = true
      return
    }
    const active = missions.find((m) => m.id === activeId)
    if (drawerOpen && active) flyToSite(viewer, active)
    else flyToOverview(viewer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId, drawerOpen])

  return (
    <div className="globe">
      <div ref={containerRef} className="globe__viewer" />
      <p className="globe__target">{hud.target}</p>
      {activeMission && telemetry && <SiteTelemetryCard ref={cardRef} mission={activeMission} telemetry={telemetry} />}
      <div className="globe__layers" role="group" aria-label="Globe layers">
        <label>
          <input
            type="checkbox"
            checked={layers.beam}
            onChange={(e) => setLayers((l) => ({ ...l, beam: e.target.checked }))}
          />
          <span>DTE LoS Beam</span>
        </label>
        <label>
          <input
            type="checkbox"
            checked={layers.solar}
            onChange={(e) => setLayers((l) => ({ ...l, solar: e.target.checked }))}
          />
          <span>Solar Vectors</span>
        </label>
      </div>
      {children && <div className="globe__dock">{children}</div>}
      <button type="button" className="globe__compare" onClick={onCompare}>
        ⇄ COMPARE SITES
      </button>
      <p className="globe__readout">{hud.readout}</p>
    </div>
  )
}
