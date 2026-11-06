import { useEffect, useRef, useState } from 'react'
import {
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
import type { Mission } from '../data/missions'
import { COMPACT_QUERY } from '../hooks/useMediaQuery'
import { fetchArtemisRegions, type ArtemisRegion } from '../services/api'
import { fetchSiteGeometry, type SiteGeometry } from '../services/siteGeometry'
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

function tileProvider(url: string, minimumLevel: number, maximumLevel?: number) {
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

export interface TelemetryOverride {
  sunElevationDeg: number
  earthElevationDeg: number
  sunVisible: boolean
  earthVisible: boolean
  sunUnitVector?: [number, number, number]
  earthUnitVector?: [number, number, number]
}

interface MoonGlobeProps {
  /** Every mission; the globe dims those outside `highlightIds`. */
  missions: Mission[]
  highlightIds: ReadonlySet<string>
  activeId: string | null
  /** When true the camera is parked over the active site with its landing ellipse drawn. */
  drawerOpen: boolean
  onSelect: (id: string) => void
  onCompare: () => void
  /** Phone layout: smaller resolution, fewer labels, bigger tap targets. */
  compact: boolean
  hud: { target: string; readout: string }
  onPinCustomSite?: (lat: number, lon: number) => void
  telemetryOverride?: TelemetryOverride | null
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

const SITE_VIEW_HEIGHT = 1_200_000

function flyToSite(viewer: Viewer, mission: Mission) {
  viewer.camera.flyTo({
    destination: Cartesian3.fromDegrees(mission.lon, mission.lat, SITE_VIEW_HEIGHT),
    orientation: { heading: 0, pitch: CesiumMath.toRadians(-80), roll: 0 },
    duration: 2.0,
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

/** Lightweight procedural Earth sprite with oceans, continents, and atmosphere rim glow. */
function earthSprite(): HTMLCanvasElement {
  const cached = sprites.get('earth_sprite')
  if (cached) return cached

  const size = 128
  const c = document.createElement('canvas')
  c.width = c.height = size
  const g = c.getContext('2d')!
  const mid = size / 2
  const r = mid - 14

  // Outer atmospheric haze glow
  const atmoGrad = g.createRadialGradient(mid, mid, r - 3, mid, mid, mid)
  atmoGrad.addColorStop(0, '#00ffff66')
  atmoGrad.addColorStop(0.4, '#0088ff28')
  atmoGrad.addColorStop(1, '#00000000')
  g.fillStyle = atmoGrad
  g.beginPath()
  g.arc(mid, mid, mid, 0, Math.PI * 2)
  g.fill()

  // Ocean disk
  const oceanGrad = g.createRadialGradient(mid - 8, mid - 8, 4, mid, mid, r)
  oceanGrad.addColorStop(0, '#3694f2')
  oceanGrad.addColorStop(0.6, '#0f4da2')
  oceanGrad.addColorStop(1, '#062058')
  g.fillStyle = oceanGrad
  g.beginPath()
  g.arc(mid, mid, r, 0, Math.PI * 2)
  g.fill()

  // Stylized landmasses
  g.fillStyle = '#4ea05d'
  g.beginPath()
  g.ellipse(mid - 4, mid - 8, 11, 17, 0.35, 0, Math.PI * 2)
  g.ellipse(mid + 12, mid + 6, 13, 9, -0.4, 0, Math.PI * 2)
  g.ellipse(mid - 15, mid + 12, 9, 13, 0.15, 0, Math.PI * 2)
  g.fill()

  // Swirling clouds
  g.strokeStyle = '#ffffffb0'
  g.lineWidth = 3
  g.beginPath()
  g.arc(mid - 2, mid - 12, 17, 0.2, 1.8)
  g.arc(mid + 6, mid + 10, 15, 2.5, 4.3)
  g.stroke()

  sprites.set('earth_sprite', c)
  return c
}

/** Lightweight stylized Sun sprite with radiant corona and flare rays. */
function sunSprite(): HTMLCanvasElement {
  const cached = sprites.get('sun_sprite')
  if (cached) return cached

  const size = 128
  const c = document.createElement('canvas')
  c.width = c.height = size
  const g = c.getContext('2d')!
  const mid = size / 2

  // Golden corona glow
  const corona = g.createRadialGradient(mid, mid, 6, mid, mid, mid)
  corona.addColorStop(0, '#ffffff')
  corona.addColorStop(0.2, '#fff176')
  corona.addColorStop(0.45, '#ff980077')
  corona.addColorStop(1, '#ff572200')
  g.fillStyle = corona
  g.fillRect(0, 0, size, size)

  // Subtle flare cross
  g.strokeStyle = '#fff8e1aa'
  g.lineWidth = 1.5
  g.beginPath()
  g.moveTo(mid, 6)
  g.lineTo(mid, size - 6)
  g.moveTo(6, mid)
  g.lineTo(size - 6, mid)
  g.stroke()

  sprites.set('sun_sprite', c)
  return c
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
  onPinCustomSite,
  telemetryOverride,
}: MoonGlobeProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const viewerRef = useRef<Viewer | null>(null)
  const selectRef = useRef(onSelect)
  selectRef.current = onSelect
  const onPinCustomRef = useRef(onPinCustomSite)
  onPinCustomRef.current = onPinCustomSite
  const mounted = useRef(false)

  // Real-time site celestial geometry & toggles
  const [geometry, setGeometry] = useState<SiteGeometry | null>(null)
  const [showDteBeam, setShowDteBeam] = useState(true)
  const [showSolarVectors, setShowSolarVectors] = useState(true)
  const [showTelemetryHud, setShowTelemetryHud] = useState(true)
  const [showArtemisRegions, setShowArtemisRegions] = useState(true)
  const [artemisRegions, setArtemisRegions] = useState<ArtemisRegion[]>([])
  const [siteHudPos, setSiteHudPos] = useState<{ x: number; y: number; visible: boolean } | null>(null)

  const activeMission = missions.find((m) => m.id === activeId)

  // Fetch Artemis III Candidate Landing Regions
  useEffect(() => {
    let active = true
    fetchArtemisRegions().then((data) => {
      if (active && data?.regions) {
        setArtemisRegions(data.regions)
      }
    })
    return () => {
      active = false
    }
  }, [])

  // Fetch or calculate instantaneous site celestial geometry
  useEffect(() => {
    if (!activeMission) {
      setGeometry(null)
      return
    }
    let isCurrent = true
    fetchSiteGeometry(activeMission.lat, activeMission.lon, activeMission.launchWindow).then((res) => {
      if (isCurrent) setGeometry(res)
    })
    return () => {
      isCurrent = false
    }
  }, [activeMission])

  // Create the viewer once.
  useEffect(() => {
    if (!containerRef.current) return

    const startsCompact = window.matchMedia(COMPACT_QUERY).matches
    const viewer = new Viewer(containerRef.current, {
      baseLayer: new ImageryLayer(tileProvider(LOCAL_TILES, 0)),
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
      if (typeof id === 'string' && /^(mission|pulse):/.test(id)) {
        selectRef.current(id.slice(id.indexOf(':') + 1))
      } else if (onPinCustomRef.current) {
        const cartesian = viewer.camera.pickEllipsoid(click.position, Ellipsoid.MOON)
        if (cartesian) {
          const carto = Ellipsoid.MOON.cartesianToCartographic(cartesian)
          const lat = CesiumMath.toDegrees(carto.latitude)
          const lon = CesiumMath.toDegrees(carto.longitude)
          onPinCustomRef.current(lat, lon)
        }
      }
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

  // Artemis III Candidate Regions (NASA Release 24-136)
  // Subtle glowing halos + labels; NEVER lander pins or boxes.
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || !showArtemisRegions || artemisRegions.length === 0) return

    const regionEntityIds: string[] = []

    artemisRegions.forEach((region) => {
      const lat = region.anchor.center_lat_deg
      const lon = region.anchor.center_lon_deg
      const diameterKm = region.anchor.diameter_km || 40
      const radiusM = Math.max(18_000, (diameterKm / 2) * 1000)

      const haloId = `artemis-halo:${region.id}`
      const labelId = `artemis-label:${region.id}`
      regionEntityIds.push(haloId, labelId)

      // Translucent glowing halo draped on lunar surface
      viewer.entities.add({
        id: haloId,
        position: Cartesian3.fromDegrees(lon, lat, 20),
        ellipse: {
          semiMajorAxis: radiusM,
          semiMinorAxis: radiusM,
          material: Color.fromCssColorString('#00d2ff').withAlpha(0.08),
          outline: true,
          outlineColor: Color.fromCssColorString('#00e5ff').withAlpha(0.45),
          height: 30,
        },
      })

      // Informative billboard text label
      viewer.entities.add({
        id: labelId,
        position: Cartesian3.fromDegrees(lon, lat, 80),
        label: {
          text: `ARTEMIS III REGION // ${region.name.toUpperCase()}`,
          font: `bold ${9 * LABEL_SS}px JetBrains Mono, monospace`,
          scale: LABEL_SCALE,
          fillColor: Color.fromCssColorString('#70e5ff'),
          style: LabelStyle.FILL,
          showBackground: true,
          backgroundColor: Color.BLACK.withAlpha(0.72),
          backgroundPadding: new Cartesian2(5 * LABEL_SS, 3 * LABEL_SS),
          pixelOffset: new Cartesian2(0, -14),
          horizontalOrigin: HorizontalOrigin.CENTER,
          verticalOrigin: VerticalOrigin.BOTTOM,
        },
      })
    })

    return () => {
      if (viewer.isDestroyed()) return
      regionEntityIds.forEach((id) => viewer.entities.removeById(id))
    }
  }, [showArtemisRegions, artemisRegions])

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
          text: `${m.name}\n${m.site}`,
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
      if (drawerOpen) {
        // Semi-transparent landing ellipse draped on the surface around the site.
        const e0 = Math.max(0.1, (active.ellipseKm?.[0] ?? 3) * 1000)
        const e1 = Math.max(0.1, (active.ellipseKm?.[1] ?? 2) * 1000)
        const semiMajor = Math.max(e0, e1)
        const semiMinor = Math.min(e0, e1)

        ids.push('ellipse:active')
        viewer.entities.add({
          id: 'ellipse:active',
          position: Cartesian3.fromDegrees(active.lon, active.lat, 0),
          ellipse: {
            semiMajorAxis: semiMajor,
            semiMinorAxis: semiMinor,
            material: ACCENT.withAlpha(0.22),
            outline: true,
            outlineColor: ACCENT,
            height: Math.max(50, (active.elevationM || 0) + 20),
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

  // Celestial augmentations: Virtual Earth model, Cyan Pulsing DTE LoS Beam, and Directional Sun
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || (!geometry && !telemetryOverride) || !activeMission) return

    const celestialIds: string[] = []

    const earthUnit = telemetryOverride?.earthUnitVector || geometry?.earth.unit_vector || [0, 0, 1]
    const earthElev = telemetryOverride ? telemetryOverride.earthElevationDeg : (geometry?.earth.elevation_deg ?? 0)
    const earthVis = telemetryOverride ? telemetryOverride.earthVisible : (geometry?.earth.visible ?? true)

    const sunUnit = telemetryOverride?.sunUnitVector || geometry?.sun.unit_vector || [1, 0, 0]
    const sunElev = telemetryOverride ? telemetryOverride.sunElevationDeg : (geometry?.sun.elevation_deg ?? 0)
    const sunVis = telemetryOverride ? telemetryOverride.sunVisible : (geometry?.sun.visible ?? true)

    // 1. Virtual Earth Model positioned in lunar sky along SPICE sub-Earth vector
    const R_EARTH = 5_800_000
    const earthPos = new Cartesian3(
      earthUnit[0] * R_EARTH,
      earthUnit[1] * R_EARTH,
      earthUnit[2] * R_EARTH,
    )

    const earthId = 'celestial:earth'
    celestialIds.push(earthId)
    viewer.entities.add({
      id: earthId,
      position: earthPos,
      billboard: {
        image: earthSprite(),
        scale: compact ? 0.38 : 0.48,
        horizontalOrigin: HorizontalOrigin.CENTER,
        verticalOrigin: VerticalOrigin.CENTER,
      },
      label: {
        text: `EARTH // DTE TARGET\nElev: ${earthElev > 0 ? '+' : ''}${earthElev.toFixed(1)}° [${earthVis ? 'ACTIVE' : 'OCCULTED'}] · RTT: ~2.56s`,
        font: `bold ${10 * LABEL_SS}px JetBrains Mono, monospace`,
        scale: LABEL_SCALE,
        fillColor: earthVis
          ? Color.fromCssColorString('#00ffff')
          : Color.fromCssColorString('#ff4d4d'),
        showBackground: true,
        backgroundColor: Color.BLACK.withAlpha(0.85),
        backgroundPadding: new Cartesian2(6 * LABEL_SS, 4 * LABEL_SS),
        pixelOffset: new Cartesian2(0, 38),
        horizontalOrigin: HorizontalOrigin.CENTER,
        verticalOrigin: VerticalOrigin.TOP,
      },
    })

    // 2. Dynamic DTE Line-of-Sight Laser Beam (Plate 02 & Plate 03)
    if (showDteBeam) {
      const beamId = 'celestial:dte-beam'
      celestialIds.push(beamId)
      const sitePos = Cartesian3.fromDegrees(activeMission.lon, activeMission.lat, 2500)

      if (earthVis) {
        // Cyan pulsing laser / RF beam
        viewer.entities.add({
          id: beamId,
          polyline: {
            positions: [sitePos, earthPos],
            width: 3.5,
            material: new PolylineGlowMaterialProperty({
              glowPower: 0.35,
              taperPower: 0.75,
              color: Color.fromCssColorString('#00ffea'),
            }),
          },
        })
      } else {
        // Red dashed vector for libration / crater rim occlusion
        viewer.entities.add({
          id: beamId,
          polyline: {
            positions: [sitePos, earthPos],
            width: 2.0,
            material: new PolylineDashMaterialProperty({
              color: Color.fromCssColorString('#ff3344').withAlpha(0.85),
              dashLength: 16,
            }),
          },
        })
      }
    }

    // 3. Lightweight Directional Sun & Solar Vector
    if (showSolarVectors) {
      const R_SUN = 7_500_000
      const sunPos = new Cartesian3(
        sunUnit[0] * R_SUN,
        sunUnit[1] * R_SUN,
        sunUnit[2] * R_SUN,
      )

      const sunId = 'celestial:sun'
      celestialIds.push(sunId)
      viewer.entities.add({
        id: sunId,
        position: sunPos,
        billboard: {
          image: sunSprite(),
          scale: compact ? 0.42 : 0.52,
          horizontalOrigin: HorizontalOrigin.CENTER,
          verticalOrigin: VerticalOrigin.CENTER,
        },
        label: {
          text: `SUN (${sunElev > 0 ? '+' : ''}${sunElev.toFixed(1)}°) [${sunVis ? 'LIT' : 'SHADOW'}]\nSOLAR VECTOR`,
          font: `${10 * LABEL_SS}px JetBrains Mono, monospace`,
          scale: LABEL_SCALE,
          fillColor: Color.fromCssColorString('#ffcc00'),
          showBackground: true,
          backgroundColor: Color.BLACK.withAlpha(0.85),
          backgroundPadding: new Cartesian2(5 * LABEL_SS, 3 * LABEL_SS),
          pixelOffset: new Cartesian2(0, 34),
          horizontalOrigin: HorizontalOrigin.CENTER,
          verticalOrigin: VerticalOrigin.TOP,
        },
      })

      const rayId = 'celestial:sun-ray'
      celestialIds.push(rayId)
      const sitePos = Cartesian3.fromDegrees(activeMission.lon, activeMission.lat, 2500)
      viewer.entities.add({
        id: rayId,
        polyline: {
          positions: [sunPos, sitePos],
          width: 1.5,
          material: Color.fromCssColorString('#ffbb00').withAlpha(0.28),
        },
      })
    }

    return () => {
      if (viewer.isDestroyed()) return
      celestialIds.forEach((id) => viewer.entities.removeById(id))
    }
  }, [geometry, telemetryOverride, activeMission, showDteBeam, showSolarVectors, compact])

  // Track site screen coordinates for floating real-time telemetry HUD overlay
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || !activeMission) {
      setSiteHudPos(null)
      return
    }

    const updateHudPos = () => {
      if (viewer.isDestroyed()) return
      const sitePos = Cartesian3.fromDegrees(activeMission.lon, activeMission.lat, 2000)
      const canvasPos = viewer.scene.cartesianToCanvasCoordinates(sitePos)
      if (!canvasPos) {
        setSiteHudPos((prev) => (prev ? { ...prev, visible: false } : null))
        return
      }

      // Check if site is facing camera or on far hemisphere
      const camPos = viewer.camera.position
      const toSite = Cartesian3.subtract(sitePos, camPos, new Cartesian3())
      const isFacing = Cartesian3.dot(viewer.camera.direction, toSite) > 0

      setSiteHudPos({
        x: canvasPos.x,
        y: canvasPos.y,
        visible: isFacing,
      })
    }

    updateHudPos()
    const removePostRender = viewer.scene.postRender.addEventListener(updateHudPos)
    return () => {
      removePostRender()
    }
  }, [activeMission])

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

      {/* Augmented Celestial & HUD Toggles */}
      <div className="globe__toggles">
        <button
          type="button"
          className={`globe__toggle-btn ${showArtemisRegions ? 'globe__toggle-btn--active' : ''}`}
          onClick={() => setShowArtemisRegions((v) => !v)}
          title="Toggle Artemis III Candidate Landing Regions (NASA Release 24-136)"
        >
          {showArtemisRegions ? '☑' : '☐'} Artemis III Regions
        </button>
        <button
          type="button"
          className={`globe__toggle-btn ${showDteBeam ? 'globe__toggle-btn--active' : ''}`}
          onClick={() => setShowDteBeam((v) => !v)}
          title="Toggle Direct-to-Earth Line-of-Sight laser beam (~2.56s RTT)"
        >
          {showDteBeam ? '☑' : '☐'} DTE LoS Beam
        </button>
        <button
          type="button"
          className={`globe__toggle-btn ${showSolarVectors ? 'globe__toggle-btn--active' : ''}`}
          onClick={() => setShowSolarVectors((v) => !v)}
          title="Toggle Directional Sun and Solar Illumination vector"
        >
          {showSolarVectors ? '☑' : '☐'} Solar Vectors
        </button>
        <button
          type="button"
          className={`globe__toggle-btn ${showTelemetryHud ? 'globe__toggle-btn--active' : ''}`}
          onClick={() => setShowTelemetryHud((v) => !v)}
          title="Toggle Real-Time Site Augmentation Markup HUD"
        >
          {showTelemetryHud ? '☑' : '☐'} Site Telemetry HUD
        </button>
      </div>

      <button type="button" className="globe__compare" onClick={onCompare}>
        ⇄ COMPARE SITES
      </button>

      {/* Dynamic 3D Site Augmentation Telemetry Markup (Plate 02 & Plate 03) */}
      {showTelemetryHud && activeMission && siteHudPos && siteHudPos.visible && geometry && (
        <div
          className="globe__hud-callout"
          style={{
            transform: `translate(${Math.round(siteHudPos.x + 18)}px, ${Math.round(siteHudPos.y - 130)}px)`,
          }}
        >
          <div className="globe__hud-header">
            <span className="globe__hud-tag">SITE HUD // {activeMission.id.toUpperCase()}</span>
            <span
              className={`globe__hud-status-badge ${
                geometry.earth.visible
                  ? 'globe__hud-status-badge--active'
                  : 'globe__hud-status-badge--occulted'
              }`}
            >
              {geometry.dte_comms.status === 'CONNECTED'
                ? `DTE: ACTIVE (${geometry.earth.elevation_deg > 0 ? '+' : ''}${geometry.earth.elevation_deg}° Earth Elev) · RTT ~2.56s`
                : `DTE: OCCULTED (${geometry.earth.elevation_deg}°) · ${geometry.dte_comms.blackout_alert || 'Alert: Blackout'}`}
            </span>
          </div>

          <div className="globe__hud-title">{activeMission.name}</div>
          <div className="globe__hud-coords">
            {activeMission.site} · {Math.abs(activeMission.lat).toFixed(2)}°S, {Math.abs(activeMission.lon).toFixed(2)}°E
          </div>

          <div className="globe__hud-metrics">
            <div className="globe__hud-row">
              <span className="globe__hud-label">PSR COLD TRAP:</span>
              <span className="globe__hud-val globe__hud-val--accent">
                {geometry.psr.standoff_str || `${geometry.psr.distance_km} km`} to {geometry.psr.nearest_name}
              </span>
            </div>
            {geometry.psr.drill_range_viable && (
              <div className="globe__hud-subbadge">
                [OPTIMAL DRILL TARGET: PRIME-1 / TRIDENT VIABLE]
              </div>
            )}
            <div className="globe__hud-row">
              <span className="globe__hud-label">LOLA HORIZON:</span>
              <span className="globe__hud-val">
                {geometry.sun.terrain_clearance_summary || `Horizon at Az ${Math.round(geometry.sun.azimuth_deg)}° is +0.5° (Clear!)`}
              </span>
            </div>
            <div className="globe__hud-row">
              <span className="globe__hud-label">ILLUMINATION:</span>
              <span className="globe__hud-val">
                {geometry.sun.elevation_deg > 0 ? `+${geometry.sun.elevation_deg}° grazing` : `${geometry.sun.elevation_deg}° night`} · {geometry.illumination.tactical_pct}% ({geometry.illumination.solar_power_status})
              </span>
            </div>
            <div className="globe__hud-row">
              <span className="globe__hud-label">VIABILITY INDEX:</span>
              <span className="globe__hud-val globe__hud-val--viability">
                {geometry.illumination.composite_viability_score ?? 88.5}% Viable [0.40Sun + 0.35DTE + 0.25Ice]
              </span>
            </div>
          </div>
        </div>
      )}

      <p className="globe__readout">{hud.readout}</p>
    </div>
  )
}
