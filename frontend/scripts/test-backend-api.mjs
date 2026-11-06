/**
 * Frontend backend API integration test.
 * Verifies connectivity, response schema, and latency from frontend to FastAPI backend.
 */
import http from 'node:http'

const BASE_URL = process.env.VITE_API_URL || 'http://127.0.0.1:8000'

function httpGet(path) {
  return new Promise((resolve, reject) => {
    const url = new URL(path, BASE_URL)
    const t0 = performance.now()
    const req = http.get(url, (res) => {
      let data = ''
      res.on('data', (chunk) => { data += chunk })
      res.on('end', () => {
        const latency = (performance.now() - t0).toFixed(2)
        try {
          const json = JSON.parse(data)
          resolve({ status: res.statusCode, headers: res.headers, data: json, latency })
        } catch {
          resolve({ status: res.statusCode, headers: res.headers, data, latency })
        }
      })
    })
    req.on('error', reject)
  })
}

async function runTests() {
  console.log(`\n======================================================`)
  console.log(`  FRONTEND -> BACKEND API INTEGRATION TEST RUNNER`)
  console.log(`  Target: ${BASE_URL}`)
  console.log(`======================================================\n`)

  let failed = 0

  // 1. Health check
  try {
    const res = await httpGet('/api/v1/health')
    if (res.status !== 200) throw new Error(`HTTP ${res.status}`)
    console.log(`✓ [PASS] Health Endpoint: status=${res.data.status}, mode=${res.data.mode}, missions=${res.data.missions_count} (${res.latency}ms)`)
  } catch (err) {
    console.error(`✗ [FAIL] Health Endpoint:`, err.message)
    failed++
  }

  // 2. Missions catalog
  try {
    const res = await httpGet('/api/v1/missions')
    if (res.status !== 200) throw new Error(`HTTP ${res.status}`)
    const missions = res.data
    if (!Array.isArray(missions) || missions.length === 0) throw new Error('Empty missions catalog')
    const sample = missions[0]
    if (!sample.id || !sample.name || typeof sample.lat !== 'number' || typeof sample.lon !== 'number') {
      throw new Error(`Invalid mission structure: ${JSON.stringify(sample)}`)
    }
    const mode = res.headers['x-data-mode'] || 'live'
    console.log(`✓ [PASS] Missions Catalog: retrieved ${missions.length} missions (X-Data-Mode: ${mode}) (${res.latency}ms)`)
  } catch (err) {
    console.error(`✗ [FAIL] Missions Catalog:`, err.message)
    failed++
  }

  // 3. Site scoring endpoint
  try {
    const res = await httpGet('/api/v1/sites/score?lat=-89.5&lon=0.0&start_date=2026-11-01&end_date=2027-02-15')
    if (res.status !== 200) throw new Error(`HTTP ${res.status}`)
    const scoreData = res.data
    if (typeof scoreData.viability_score !== 'number' && typeof scoreData.scores?.total_viability_score !== 'number') {
      throw new Error('Missing viability score in response')
    }
    const cache = res.headers['x-cache'] || 'UNKNOWN'
    console.log(`✓ [PASS] Site Scoring: Shackleton Rim viability=${scoreData.viability_score ?? (scoreData.scores.total_viability_score * 100).toFixed(1)}% (X-Cache: ${cache}) (${res.latency}ms)`)
  } catch (err) {
    console.error(`✗ [FAIL] Site Scoring:`, err.message)
    failed++
  }

  // 4. Hard-gate PSR crater floor evaluation
  try {
    const res = await httpGet('/api/v1/sites/score?lat=-89.9&lon=0.0&permanently_shadowed=true')
    if (res.status !== 200) throw new Error(`HTTP ${res.status}`)
    const psrData = res.data
    if (psrData.scores.solar_viability !== 0 || psrData.scores.total_viability_score !== 0) {
      throw new Error(`Hard-gate failure: total score not zero (${JSON.stringify(psrData.scores)})`)
    }
    console.log(`✓ [PASS] Hard-Gate PSR Validation: zero solar power correctly forced total score to 0.0 (${res.latency}ms)`)
  } catch (err) {
    console.error(`✗ [FAIL] Hard-Gate PSR:`, err.message)
    failed++
  }

  // 5. Communications endpoint
  try {
    const res = await httpGet('/api/v1/sites/comms?lat=-89.5&lon=0.0')
    if (res.status !== 200) throw new Error(`HTTP ${res.status}`)
    const commsData = res.data
    if (typeof commsData.earth_comms_viability !== 'number') {
      throw new Error('Missing earth_comms_viability in comms response')
    }
    console.log(`✓ [PASS] Site Comms: Earth viability=${commsData.earth_comms_viability}, direct_possible=${commsData.direct_to_earth_possible} (${res.latency}ms)`)
  } catch (err) {
    console.error(`✗ [FAIL] Site Comms:`, err.message)
    failed++
  }

  // 6. Site celestial geometry & augmentation endpoint
  try {
    const res = await httpGet('/api/v1/sites/geometry?lat=-84.79&lon=29.20&start_date=2026-11-01')
    if (res.status !== 200) throw new Error(`HTTP ${res.status}`)
    const geomData = res.data
    if (!geomData.earth || !geomData.sun || !geomData.psr || !geomData.illumination || !geomData.dte_comms) {
      throw new Error(`Incomplete geometry response contract: ${Object.keys(geomData)}`)
    }
    console.log(`✓ [PASS] Site Celestial Geometry: Earth Elev=${geomData.earth.elevation_deg}°, Sun Elev=${geomData.sun.elevation_deg}°, Nearest PSR=${geomData.psr.nearest_name} (${geomData.psr.distance_km}km), DTE=${geomData.dte_comms.status} (${res.latency}ms)`)
  } catch (err) {
    console.error(`✗ [FAIL] Site Celestial Geometry:`, err.message)
    failed++
  }

  console.log(`\n------------------------------------------------------`)
  if (failed === 0) {
    console.log(`  >>> ALL FRONTEND -> BACKEND API TESTS PASSED <<<`)
    console.log(`------------------------------------------------------\n`)
  } else {
    console.error(`  >>> ${failed} TEST(S) FAILED <<<`)
    console.log(`------------------------------------------------------\n`)
    process.exitCode = 1
  }
}

runTests()
