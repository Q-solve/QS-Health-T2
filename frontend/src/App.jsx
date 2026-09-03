import React, { useEffect, useMemo, useState } from "react";
import {
  fetchConstraints,
  fetchHealth,
  fetchLadder,
  fetchFeatures,
  fetchScalingBenchmarks,
  fetchSharedBenchmarks,
  fetchPairedBenchmarks,
  fetchObjectiveCompare,
  fetchVerdict,
  fetchDatasetInventory,
  fetchClassicalEvaluation,
  previewScenario,
  solveInteractive,
} from "./api/client";
import OptimizeForm, { DEFAULT_METHODS } from "./components/OptimizeForm";
import SideBySideResults from "./components/SideBySideResults";
import ScalingChart from "./components/ScalingChart";
import SharedBenchmarkPanel from "./components/SharedBenchmarkPanel";
import ClassicalEvaluationPanel from "./components/ClassicalEvaluationPanel";
import ObjectiveCompareTable from "./components/ObjectiveCompareTable";
import VerdictBanner from "./components/VerdictBanner";
import "./styles.css";

export default function App() {
  const [health, setHealth] = useState(null);
  const [ladder, setLadder] = useState(null);
  const [constraints, setConstraints] = useState(null);
  const [factorCatalog, setFactorCatalog] = useState([]);
  const [enabledFactors, setEnabledFactors] = useState([]);
  const [form, setForm] = useState({
    mode: "classical",
    include_quantum: false,
    county: "TURKANA",
    tier: "T1",
    constraint_setting: "nominal",
    feature_stage: "B4",
    seed: 42,
    time_budget_sec: 10,
    who_capacity_mode: "feasible",
    num_chws_total: "",
    max_walking_dist_km: 7.5,
    who_ratio: 1000,
    equity_target: 0.25,
  });
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("optimize");
  const [scaling, setScaling] = useState(null);
  const [shared, setShared] = useState(null);
  const [paired, setPaired] = useState(null);
  const [verdict, setVerdict] = useState(null);
  const [inventory, setInventory] = useState(null);
  const [evaluation, setEvaluation] = useState(null);
  const [objectiveCompare, setObjectiveCompare] = useState(null);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth(null));
    fetchLadder()
      .then((data) => {
        setLadder(data);
        if (data.counties?.length && !data.counties.includes(form.county)) {
          setForm((f) => ({ ...f, county: data.counties[0] }));
        }
        if (data.demand_factors?.length) {
          setFactorCatalog(data.demand_factors);
          setEnabledFactors(
            data.default_enabled_factors || data.demand_factors.map((f) => f.id)
          );
        }
      })
      .catch((e) => setError(String(e.message || e)));
    fetchConstraints()
      .then((c) => {
        setConstraints(c);
        if (c?.defaults) {
          setForm((f) => ({
            ...f,
            max_walking_dist_km: c.defaults.max_walking_dist_km,
            who_ratio: c.defaults.who_ratio,
            equity_target: c.defaults.equity_target,
          }));
        }
      })
      .catch(() => {});
    fetchFeatures()
      .then((feat) => {
        if (feat?.factors?.length && !factorCatalog.length) {
          setFactorCatalog(feat.factors);
          setEnabledFactors(feat.default_enabled_factors || feat.factors.map((f) => f.id));
        }
      })
      .catch(() => {});
    fetchScalingBenchmarks().then(setScaling).catch(() => setScaling(null));
    fetchSharedBenchmarks().then(setShared).catch(() => setShared(null));
    fetchPairedBenchmarks().then(setPaired).catch(() => setPaired(null));
    fetchVerdict().then(setVerdict).catch(() => setVerdict(null));
    fetchDatasetInventory().then(setInventory).catch(() => setInventory(null));
    fetchClassicalEvaluation().then(setEvaluation).catch(() => setEvaluation(null));
    fetchObjectiveCompare().then(setObjectiveCompare).catch(() => setObjectiveCompare(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const requestBody = useMemo(
    () => {
      const body = {
        tier: form.tier,
        county: form.county,
        constraint_setting: form.constraint_setting,
        feature_stage: form.feature_stage,
        seed: form.seed,
        time_budget_sec: form.time_budget_sec,
        who_capacity_mode: form.who_capacity_mode,
        mode: form.include_quantum ? "both" : "classical",
        classical_include:
          form.tier === "T0"
            ? [...DEFAULT_METHODS, "c1_brute_force"]
            : DEFAULT_METHODS,
        max_walking_dist_km: form.max_walking_dist_km,
        who_ratio: form.who_ratio,
        equity_target: form.equity_target,
        enabled_factors: enabledFactors,
      };
      const n = Number(form.num_chws_total);
      if (form.who_capacity_mode === "user" && Number.isFinite(n) && n > 0) {
        body.num_chws_total = Math.floor(n);
        body.who_capacity_mode = "user";
      }
      return body;
    },
    [form, enabledFactors]
  );

  const handlePreview = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await previewScenario(requestBody);
      setPreview(data);
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError("");
    setTab("optimize");
    try {
      const data = await solveInteractive(requestBody);
      setResult(data);
      setPreview({ scenario: data.scenario });
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="hero">
        <p className="brand">AfyaDeploy</p>
        <h1>Community health worker deployment for rural Kenya</h1>
        <p className="tagline">
          Assign community units to facility hubs under your walking distance, staffing, and fairness
          limits — using verified county data.
        </p>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <div className="meta-bar">
        <span>{health?.target_counties_count ?? 14} priority counties</span>
        <span>Verified facility & community data</span>
        <span>Classical planning on your constraints</span>
      </div>

      <nav className="tabs" aria-label="Main sections">
        {[
          ["optimize", "Plan deployment"],
          ["benchmarks", "Published results"],
          ["data", "About the data"],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`tab ${tab === id ? "active" : ""}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === "optimize" && (
        <div className="layout">
          <aside className="stack">
            <OptimizeForm
              ladder={ladder}
              constraints={constraints}
              form={form}
              setForm={setForm}
              enabledFactors={enabledFactors}
              setEnabledFactors={setEnabledFactors}
              factorCatalog={factorCatalog}
              preview={preview}
              onPreview={handlePreview}
              onSubmit={handleSubmit}
              loading={loading}
            />
          </aside>
          <div className="stack grow">
            <SideBySideResults result={result} />
          </div>
        </div>
      )}

      {tab === "benchmarks" && (
        <div className="stack">
          <VerdictBanner verdict={verdict} />
          <ObjectiveCompareTable compare={objectiveCompare} />
          <ClassicalEvaluationPanel evaluation={evaluation} />
          <ScalingChart records={scaling?.records} />
          <SharedBenchmarkPanel shared={shared} paired={paired} />
        </div>
      )}

      {tab === "data" && (
        <section className="panel">
          <h2>How the dataset is used</h2>
          <p className="muted tight">
            Facilities and community units come from the unified Kenya dataset. You choose which need
            factors raise urgency; geography (terrain, flood, walking distance) always shapes travel.
          </p>
          <ul className="recs">
            <li>
              <strong>Combined constraints:</strong> walking distance, people-per-CHW capacity, and
              fairness always enter one shared objective score — not separate one-to-one solvers.
            </li>
            <li>
              <strong>Demand (you choose):</strong> vulnerability, under-5 share, nutrition, maternal
              coverage, malaria/ITN, flood flags, poverty, and related columns combine into community
              urgency.
            </li>
            <li>
              <strong>Geography (always on):</strong> facility and community coordinates, terrain
              class, and access friction set walking distances.
            </li>
            <li>
              <strong>Capacity:</strong> set total CHWs yourself, or auto-scale headcount so WHO
              staffing can be met under your people-per-CHW limit.
            </li>
          </ul>
          <h3>Data files</h3>
          <ul className="file-list">
            {Object.entries(inventory?.files || {}).map(([name, meta]) => (
              <li key={name} className={meta.exists ? "ok" : "missing"}>
                {name}
                {meta.exists ? ` · ${(meta.bytes / 1024).toFixed(0)} KB` : " (missing)"}
              </li>
            ))}
          </ul>
        </section>
      )}

      <footer className="footer">
        SDG 3 · Community health worker coverage for Kenya&apos;s priority counties
      </footer>
    </div>
  );
}
