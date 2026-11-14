import { useEffect, useState, type RefObject } from 'react'
import { Cartesian2, Math as CesiumMath, Matrix4, Transforms, type Viewer } from 'cesium'
import './GlobeControls.css'

// Same limits as the mouse/touch controller (MoonGlobe sets them on the scene).
const MIN_HEIGHT_M = 1_500
const MAX_HEIGHT_M = 12_000_000
// Never tilt past this, so the camera can't end up looking along or under the surface.
const FLATTEST_PITCH_DEG = -8
const TILT_STEP_DEG = 15
const HINTS_KEY = 'apolloharness.cameraHints.seen'

function cameraHeight(viewer: Viewer): number {
  return viewer.scene.globe.ellipsoid.cartesianToCartographic(viewer.camera.position)?.height ?? MAX_HEIGHT_M
}

function zoom(viewer: Viewer, inward: boolean) {
  const h = cameraHeight(viewer)
  if (inward) viewer.camera.zoomIn(Math.max(0, Math.min(h * 0.45, h - MIN_HEIGHT_M)))
  else viewer.camera.zoomOut(Math.max(0, Math.min(h * 0.8, MAX_HEIGHT_M - h)))
}

/** Tilt about the surface point at the centre of the view (towards or away from the horizon). */
function tilt(viewer: Viewer, towardHorizon: boolean) {
  const { scene, camera } = viewer
  const canvas = scene.canvas
  const ray = camera.getPickRay(new Cartesian2(canvas.clientWidth / 2, canvas.clientHeight / 2))
  const center = ray ? scene.globe.pick(ray, scene) : undefined
  if (!center) return
  const before = { destination: camera.position.clone(), orientation: { heading: camera.heading, pitch: camera.pitch, roll: camera.roll } }
  camera.lookAtTransform(Transforms.eastNorthUpToFixedFrame(center, scene.globe.ellipsoid))
  const angle = CesiumMath.toRadians(TILT_STEP_DEG)
  if (towardHorizon) camera.rotateDown(angle)
  else camera.rotateUp(angle)
  camera.lookAtTransform(Matrix4.IDENTITY)
  if (camera.pitch > CesiumMath.toRadians(FLATTEST_PITCH_DEG)) camera.setView(before)
}

function readSeen(): boolean {
  try {
    return window.localStorage.getItem(HINTS_KEY) === '1'
  } catch {
    return false
  }
}

function markSeen() {
  try {
    window.localStorage.setItem(HINTS_KEY, '1')
  } catch {
    // Private mode / blocked storage: the hints just show again next visit.
  }
}

const MOUSE_HINTS: [string, string][] = [
  ['Drag', 'Rotate the Moon'],
  ['Scroll  ·  Right-drag', 'Zoom'],
  ['Ctrl + drag  ·  Middle-drag', 'Tilt towards the horizon'],
  ['Shift + drag', 'Look around from where you are'],
  ['Click a pin', 'Open that mission'],
]

const TOUCH_HINTS: [string, string][] = [
  ['One finger', 'Rotate the Moon'],
  ['Pinch', 'Zoom'],
  ['Two fingers up / down', 'Tilt towards the horizon'],
  ['Tap a pin', 'Open that mission'],
]

interface Props {
  viewerRef: RefObject<Viewer | null>
  onReset: () => void
}

export function GlobeControls({ viewerRef, onReset }: Props) {
  const [hintsOpen, setHintsOpen] = useState(() => !readSeen())
  const [touch] = useState(() => window.matchMedia('(pointer: coarse)').matches)

  const close = () => {
    setHintsOpen(false)
    markSeen()
  }

  useEffect(() => {
    if (!hintsOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      setHintsOpen(false)
      markSeen()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [hintsOpen])

  const act = (fn: (viewer: Viewer) => void) => () => {
    const viewer = viewerRef.current
    if (viewer && !viewer.isDestroyed()) fn(viewer)
  }

  const hints = touch ? TOUCH_HINTS : MOUSE_HINTS

  return (
    <>
      <div className="globe-ctl" role="toolbar" aria-label="Camera controls">
        <button type="button" onClick={act((v) => zoom(v, true))} aria-label="Zoom in" title="Zoom in">
          <Icon d="M8 3v10M3 8h10" />
        </button>
        <button type="button" onClick={act((v) => zoom(v, false))} aria-label="Zoom out" title="Zoom out">
          <Icon d="M3 8h10" />
        </button>
        <span className="globe-ctl__sep" />
        <button type="button" onClick={act((v) => tilt(v, true))} aria-label="Tilt towards the horizon" title="Tilt towards the horizon">
          <Icon d="M2 12h12M4 9l4-4 4 4" />
        </button>
        <button type="button" onClick={act((v) => tilt(v, false))} aria-label="Tilt back to top-down" title="Tilt back to top-down">
          <Icon d="M2 12h12M4 5l4 4 4-4" />
        </button>
        <span className="globe-ctl__sep" />
        <button type="button" onClick={onReset} aria-label="Reset view" title="Reset view">
          <Icon d="M3.5 8a4.5 4.5 0 1 0 1.3-3.2M3.5 2.5v2.8h2.8" />
        </button>
        <button
          type="button"
          className={hintsOpen ? 'is-on' : undefined}
          onClick={() => (hintsOpen ? close() : setHintsOpen(true))}
          aria-label="How to move the camera"
          aria-expanded={hintsOpen}
          title="How to move the camera"
        >
          <span className="globe-ctl__q">?</span>
        </button>
      </div>

      {hintsOpen && (
        <div className="globe-hints" role="dialog" aria-label="Camera controls">
          <p className="globe-hints__title">Explore the Moon your way</p>
          <dl>
            {hints.map(([gesture, effect]) => (
              <div key={gesture}>
                <dt>{gesture}</dt>
                <dd>{effect}</dd>
              </div>
            ))}
          </dl>
          <p className="globe-hints__note">The buttons on the right do the same. Reset brings back the starting view.</p>
          <button type="button" className="globe-hints__ok" onClick={close}>
            Got it
          </button>
        </div>
      )}
    </>
  )
}

function Icon({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  )
}
