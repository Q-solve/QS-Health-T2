const TIER_LABELS = {
  T0: "Tiny cluster (2 facilities × 3 communities)",
  T1: "Small cluster (3 × 4)",
  T2: "Medium cluster (4 × 5)",
  T3: "Large cluster (6 × 6)",
  T4: "Extra-large cluster (6 × 9)",
  T5: "Whole county",
  T6: "Multi-county region",
};

const DEFAULT_METHODS = [
  "c2_milp",
  "c3_greedy",
  "c4_local_search",
  "c5_simulated_annealing",
  "c7_tabu_search",
];

function groupFactors(factors) {
  const groups = {};
  for (const f of factors || []) {
    const g = f.group || "Other";
    if (!groups[g]) groups[g] = [];
    groups[g].push(f);
  }
  return groups;
}

export default function OptimizeForm({
  ladder,
  constraints,
  form,
  setForm,
  enabledFactors,
  setEnabledFactors,
  factorCatalog,
  preview,
  onPreview,
  onSubmit,
  loading,
}) {
  const counties = ladder?.counties || ladder?.target_counties || [];
  const tiers = Object.keys(ladder?.tier_labels || ladder?.tiers || TIER_LABELS);
  const tierLabels = ladder?.tier_labels || TIER_LABELS;
  const grouped = groupFactors(factorCatalog);
  const autoScale = form.who_capacity_mode === "feasible";

  const update = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const applyPreset = (name) => {
    const d = constraints?.detail?.[name];
    if (!d) return;
    setForm((f) => ({
      ...f,
      constraint_setting: name,
      max_walking_dist_km: d.max_walking_dist_km,
      who_ratio: d.who_ratio,
      equity_target: d.equity_target,
    }));
  };

  const toggleFactor = (id) => {
    setEnabledFactors((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const selectAllFactors = () =>
    setEnabledFactors((factorCatalog || []).map((f) => f.id));
  const selectCoreFactors = () =>
    setEnabledFactors(
      (factorCatalog || [])
        .filter((f) => ["Access & need", "Workforce gap", "Terrain & travel"].includes(f.group))
        .map((f) => f.id)
    );

  return (
    <section className="panel optimize-form">
      <h2>Plan a deployment</h2>
      <p className="muted tight">
        Walk, staffing, and fairness limits are applied together in one score. Need factors from the
        county dataset combine into community urgency — use all of them to stress-test beyond simple
        one-to-one relationships.
      </p>

      <div className="form-section">
        <h3 className="section-title">Location & size</h3>
        <div className="form-grid">
          <label className="field">
            <span>County</span>
            <select value={form.county} onChange={(e) => update("county", e.target.value)} disabled={loading}>
              {counties.map((c) => (
                <option key={c} value={c}>
                  {c.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Problem size</span>
            <select value={form.tier} onChange={(e) => update("tier", e.target.value)} disabled={loading}>
              {tiers.map((t) => (
                <option key={t} value={t}>
                  {tierLabels[t] || TIER_LABELS[t] || t}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="form-section">
        <div className="method-head">
          <h3 className="section-title">Constraint package (combined)</h3>
          <div className="link-row wrap">
            {(constraints?.presets || ["loose", "nominal", "tight"]).map((p) => (
              <button
                key={p}
                type="button"
                className={`chip ${form.constraint_setting === p ? "active" : ""}`}
                onClick={() => applyPreset(p)}
                disabled={loading}
              >
                {p === "loose" ? "Relaxed" : p === "tight" ? "Strict" : "Standard"}
              </button>
            ))}
          </div>
        </div>
        <p className="muted tight">
          Walking distance, people-per-CHW, and fairness always enter the same objective — not as
          separate solvers.
        </p>
        <div className="form-grid">
          <label className="field">
            <span>Max walking distance (km)</span>
            <input
              type="number"
              min={1}
              step={0.5}
              value={form.max_walking_dist_km}
              onChange={(e) => update("max_walking_dist_km", Number(e.target.value))}
              disabled={loading}
            />
          </label>

          <label className="field">
            <span>People per CHW</span>
            <input
              type="number"
              min={100}
              step={50}
              value={form.who_ratio}
              onChange={(e) => update("who_ratio", Number(e.target.value))}
              disabled={loading}
            />
          </label>

          <label className="field">
            <span>Fairness target (0–1, lower = fairer)</span>
            <input
              type="number"
              min={0.05}
              max={0.95}
              step={0.01}
              value={form.equity_target}
              onChange={(e) => update("equity_target", Number(e.target.value))}
              disabled={loading}
            />
          </label>

          <label className="field">
            <span>Search time per method (seconds)</span>
            <input
              type="number"
              min={1}
              step={1}
              value={form.time_budget_sec}
              onChange={(e) => update("time_budget_sec", Number(e.target.value))}
              disabled={loading}
            />
          </label>
        </div>
      </div>

      <div className="form-section">
        <h3 className="section-title">CHW workforce</h3>
        <label className="check capacity-toggle">
          <input
            type="checkbox"
            checked={autoScale}
            onChange={(e) => {
              const on = e.target.checked;
              setForm((f) => ({
                ...f,
                who_capacity_mode: on ? "feasible" : "user",
                num_chws_total: on ? "" : f.num_chws_total || "",
              }));
            }}
            disabled={loading}
          />
          Auto-scale headcount to WHO-feasible (recommended)
        </label>
        <div className="form-grid">
          <label className="field">
            <span>Total CHWs available</span>
            <input
              type="number"
              min={1}
              step={1}
              placeholder={autoScale ? "Auto from population" : "e.g. 24"}
              value={form.num_chws_total}
              onChange={(e) => {
                const v = e.target.value;
                setForm((f) => ({
                  ...f,
                  num_chws_total: v,
                  who_capacity_mode: v ? "user" : f.who_capacity_mode,
                }));
              }}
              disabled={loading || autoScale}
            />
          </label>
          <div className="field hint-field">
            <span>How this works</span>
            <p className="muted tight no-margin">
              This number is staff seats split across hubs — not a list of named workers. Leave
              auto-scale on if you want enough seats to meet your people-per-CHW limit.
            </p>
          </div>
        </div>
        <label className="check capacity-toggle">
          <input
            type="checkbox"
            checked={!!form.include_quantum}
            onChange={(e) => update("include_quantum", e.target.checked)}
            disabled={loading}
          />
          Also run QAOA (quantum comparator) — only fits Tiny–Extra-large clusters, not whole county
        </label>
      </div>

      <div className="form-section">
        <div className="method-head">
          <h3 className="section-title">Need factors (combined into urgency)</h3>
          <div className="link-row">
            <button type="button" className="linkish" onClick={selectAllFactors} disabled={loading}>
              All
            </button>
            <button type="button" className="linkish" onClick={selectCoreFactors} disabled={loading}>
              Core only
            </button>
          </div>
        </div>
        <p className="muted tight">
          Checked columns from the unified dataset raise urgency together (equal-weight average).
          Terrain and walking distance always apply to travel.
        </p>
        {Object.entries(grouped).map(([group, items]) => (
          <div key={group} className="factor-group card-block">
            <h4>{group}</h4>
            <div className="factor-grid">
              {items.map((f) => (
                <label key={f.id} className="check factor-check" title={f.description}>
                  <input
                    type="checkbox"
                    checked={enabledFactors.includes(f.id)}
                    onChange={() => toggleFactor(f.id)}
                    disabled={loading}
                  />
                  {f.label}
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>

      {preview?.scenario && (
        <div className="preview-box card-block">
          <strong>Ready to solve</strong>
          <dl className="kv">
            <div>
              <dt>Facilities</dt>
              <dd>{preview.scenario.num_facilities}</dd>
            </div>
            <div>
              <dt>Communities</dt>
              <dd>{preview.scenario.num_communities}</dd>
            </div>
            <div>
              <dt>Walk limit</dt>
              <dd>{preview.scenario.max_walking_dist_km} km</dd>
            </div>
            <div>
              <dt>People / CHW</dt>
              <dd>1:{preview.scenario.who_ratio}</dd>
            </div>
            <div>
              <dt>Need factors</dt>
              <dd>{(preview.scenario.enabled_factors || []).length}</dd>
            </div>
            <div>
              <dt>CHWs at hubs</dt>
              <dd>{preview.scenario.num_chws_available} seats (not named workers)</dd>
            </div>
            <div>
              <dt>QAOA qubits</dt>
              <dd>
                {preview.scenario.num_variables}
                {preview.scenario.quantum_recommended ? " (fits)" : " (too large — classical only)"}
              </dd>
            </div>
          </dl>
        </div>
      )}

      <div className="action-row">
        <button type="button" className="secondary" onClick={onPreview} disabled={loading}>
          Preview
        </button>
        <button
          type="button"
          className="primary"
          onClick={onSubmit}
          disabled={loading || enabledFactors.length === 0}
        >
          {loading ? "Finding best plan…" : "Find best deployment"}
        </button>
      </div>
    </section>
  );
}

export { DEFAULT_METHODS, TIER_LABELS };
