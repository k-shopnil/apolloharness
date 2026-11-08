import { useEffect } from 'react'
import elevationChart from '../assets/elevation-chart.svg'
import spiceChart from '../assets/spice-chart.svg'
import check from '../assets/check.svg'
import { pdsProducts } from '../data/provenance'
import './ProvenanceModal.css'

interface ProvenanceModalProps {
  onClose: () => void
}

export function ProvenanceModal({ onClose }: ProvenanceModalProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="modal" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal__dialog" role="dialog" aria-modal="true" aria-labelledby="pds-title">
        <header className="modal__header">
          <div>
            <p className="modal__eyebrow">EVIDENCE &amp; DATA PROVENANCE</p>
            <h2 id="pds-title">{'// NASA PDS ARCHIVE'}</h2>
          </div>
          <button type="button" className="modal__close" onClick={onClose}>
            [ ✕ CLOSE ]
          </button>
        </header>

        <div className="modal__body">
          <section className="panel panel--elevation">
            <h3>A // LRO LOLA ELEVATION CROSS-SECTION (20M DEM)</h3>
            <p>Crater rim to floor traverse through landing ellipse center</p>
            <div className="chart chart--tall">
              <img src={elevationChart} alt="Elevation cross-section" />
              <span className="chart__tag" style={{ left: '43.9%', right: '20.1%', top: 8 }}>
                <i /> ELLIPSE CENTER (POINT ALPHA)
              </span>
            </div>
            <div className="panel__legend">
              <span>CRATER RIM (W) [+1380M]</span>
              <span>CRATER FLOOR [-4120M]</span>
              <span className="panel__legend--hi">RIDGE (E) [+1120M]</span>
            </div>
          </section>

          <section className="panel">
            <h3>B // NAIF SPICE EARTH LINE-OF-SIGHT ELEVATION (29.5-DAY CYCLE)</h3>
            <p>Earth elevation angle from Mons Mouton over one synodic period</p>
            <div className="chart chart--short">
              <img src={spiceChart} alt="Earth line-of-sight elevation" />
              <span className="chart__label chart__label--tl">90° ZENITH</span>
              <span className="chart__label chart__label--bl">0° HORIZON (LOS LIMIT)</span>
              <span className="chart__label chart__label--br">+29.5 DAYS (SYNODIC END)</span>
              <span className="chart__tag chart__tag--plain" style={{ left: '38%', right: '35.2%', top: 8 }}>
                PEAK APOGEE: +8.2° LOS
              </span>
            </div>
          </section>

          <section className="ids">
            <div className="ids__head">
              <h3>C // NASA PDS PRODUCT IDENTIFIERS</h3>
              <span>FORMAT: PDS4 ARCHIVE STANDARDS</span>
            </div>
            {pdsProducts.map((p) => (
              <div className="ids__row" key={p.label}>
                <strong>{p.label}</strong>
                <span>{p.urn}</span>
              </div>
            ))}
          </section>

          <div className="verify">
            <span className="verify__badge">
              <img src={check} alt="" width={9.1} height={9.42} />
            </span>
            <div>
              <strong>Deterministic Python Compute Boundary Verified</strong>
              <p>Zero AI Hallucination · All values derived from NASA PDS archives via deterministic pipeline</p>
            </div>
          </div>
        </div>

        <footer className="modal__footer">
          <span>HASH: SHA256-D7E2B89...419A</span>
          <span className="modal__status">STATUS: VERIFIED PDS GOLD RECORD</span>
        </footer>
      </div>
    </div>
  )
}
