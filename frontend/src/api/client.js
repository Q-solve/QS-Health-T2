// Local Vite proxy uses "/api". On Vercel set VITE_API_BASE_URL to the Render
// service origin, e.g. https://afyadeploy-api.onrender.com (no trailing slash).
const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const API_BASE = API_ORIGIN ? `${API_ORIGIN}/api` : "/api";

async function getJson(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(detail || `Request failed: ${path}`);
  }
  return res.json();
}

async function postJson(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = "";
    try {
      const j = await res.json();
      detail = j.detail || JSON.stringify(j);
    } catch {
      detail = await res.text().catch(() => "");
    }
    throw new Error(detail || `Request failed: ${path}`);
  }
  return res.json();
}

export const fetchHealth = () => getJson("/health");
export const fetchScenarios = () => getJson("/scenarios");
export const fetchScenarioDetail = (name) => getJson(`/scenario/${encodeURIComponent(name)}`);
export const fetchClassicalMethods = () => getJson("/solve/classical/methods");
export const fetchQBraidDevices = () => getJson("/qbraid/devices");
export const fetchScalingBenchmarks = () => getJson("/benchmarks/scaling");
export const fetchSharedBenchmarks = () => getJson("/benchmarks/shared");
export const fetchPairedBenchmarks = () => getJson("/benchmarks/paired");
export const fetchObjectiveCompare = () => getJson("/benchmarks/objective-compare");
export const fetchVerdict = () => getJson("/verdict");
export const fetchDatasetInventory = () => getJson("/dataset/inventory");
export const fetchClassicalEvaluation = () => getJson("/benchmarks/classical-evaluation");
export const fetchJudging = () => getJson("/judging/criteria");
export const fetchLadder = () => getJson("/ladder");
export const fetchConstraints = () => getJson("/constraints");
export const fetchFeatures = () => getJson("/features");

export function previewScenario(body) {
  return postJson("/scenario/preview", body);
}

export function solveInteractive(body) {
  return postJson("/solve/interactive", body);
}

export function solveCompare({
  scenarioName,
  backendName,
  runQuantum = false,
  classicalBudgetSec = 10,
  seed = 42,
  classicalInclude = null,
}) {
  return postJson("/solve/compare", {
    scenario_name: scenarioName,
    backend_name: backendName,
    run_quantum: runQuantum,
    classical_budget_sec: classicalBudgetSec,
    seed,
    classical_include: classicalInclude,
  });
}

export function predictQMLDemand(vulnerability, distanceKm, diseaseRisk) {
  return postJson("/qml/compare_demand", {
    vulnerability_score: vulnerability,
    distance_km: distanceKm,
    disease_risk: diseaseRisk,
  });
}
