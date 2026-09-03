import ResultsCharts from "./ResultsCharts";

const METHOD_LABELS = {
  c1_brute_force: "Exact (tiny problems)",
  c2_milp: "Exact / mathematical",
  c3_greedy: "Nearest hub",
  c4_local_search: "Local improvement",
  c5_simulated_annealing: "Annealing search",
  c6_genetic_algorithm: "Population search",
  c7_tabu_search: "Tabu search",
  qaoa_qbraid: "QAOA (quantum)",
};

function fmt(v, digits = 2) {
  if (v == null || Number.isNaN(Number(v))) return "—";
  return Number(v).toFixed(digits);
}

export default function SideBySideResults({ result }) {
  if (!result?.solved) {
    return (
      <section className="panel results-empty">
        <h2>Results</h2>
        <p className="muted">
          Set county, combined walk/staffing/fairness limits, total CHWs, and need factors — then find
          the best deployment plan. Charts will explain how methods and communities compare.
        </p>
      </section>
    );
  }

  const sc = result.scenario || {};
  const ranking = result.classical?.ranking_by_objective || [];
  const bestId = result.classical?.best_classical;
  const best = bestId ? (result.classical?.results || {})[bestId] : null;
  const assignments = best?.assignments || [];
  const quantum = result.quantum || null;
  const qres = quantum?.result;
  const extra = sc.extra || {};
  const requestedChws = extra.requested_total_chws ?? extra.user_total_chws ?? sc.requested_total_chws;
  const packingOk = extra.packing_ok ?? sc.packing_ok;
  const staffedHubs = (sc.facilities || []).filter((f) => (f.available_chws || 0) > 0);

  return (
    <div className="stack">
      <section className="panel">
        <h2>Deployment plan</h2>
        <p className="muted tight">
          {sc.county} · {(sc.num_facilities || 0)} facilities · {(sc.num_communities || 0)} communities
          · {sc.num_chws_available ?? "—"} CHWs
        </p>
        <div className="stat-row">
          <div className="stat">
            <span className="stat-val">{fmt(best?.population_coverage_pct, 1)}%</span>
            <span className="stat-lab">Population covered</span>
          </div>
          <div className="stat">
            <span className="stat-val">{fmt(best?.total_travel_km, 1)}</span>
            <span className="stat-lab">Total travel (km)</span>
          </div>
          <div className="stat">
            <span className="stat-val">{fmt(best?.gini_equity_index, 3)}</span>
            <span className="stat-lab">Fairness (Gini)</span>
          </div>
          <div className="stat">
            <span className="stat-val">{fmt(best?.who_compliance_pct, 1)}%</span>
            <span className="stat-lab">Staffing compliance</span>
          </div>
        </div>
        {result.hurdle?.note && (
          <p className="muted tight hurdle-note">{result.hurdle.note}</p>
        )}
        <p className="muted tight">
          {sc.num_chws_available ?? "—"} CHW seats are the staffing budget split across hubs
          {requestedChws != null ? ` (you entered ${requestedChws})` : ""}. The table below
          lists community→hub links, not {sc.num_chws_available ?? "N"} named workers.
          {(packingOk === false)
            ? " This headcount cannot cover every community at the people-per-CHW limit — overflow is expected."
            : ""}
        </p>
        {quantum?.skipped && quantum?.reason && (
          <p className="muted tight hurdle-note">{quantum.reason}</p>
        )}
        {qres && result.side_by_side && (
          <p className="muted tight">
            QAOA score {fmt(result.side_by_side.quantum_H)} vs best classical{" "}
            {fmt(result.side_by_side.classical_H)} ({METHOD_LABELS[result.side_by_side.classical_solver] ||
              result.side_by_side.classical_solver}
            ). Lower is better
            {result.side_by_side.qaoa_beats_best_classical ? " — QAOA is ahead on this instance." : " — classical is ahead or tied."}
          </p>
        )}
      </section>

      <ResultsCharts result={result} />

      {assignments.length > 0 && (
        <section className="panel">
          <h2>Recommended links</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Community</th>
                  <th>Facility hub</th>
                  <th>Walk (km)</th>
                  <th>Need covered</th>
                </tr>
              </thead>
              <tbody>
                {assignments.map((a) => (
                  <tr key={`${a.facility_id}-${a.community_id}`}>
                    <td>{a.community_name}</td>
                    <td>{a.facility_name}</td>
                    <td>{fmt(a.walking_distance_km, 1)}</td>
                    <td>{a.demand_covered}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {ranking.length > 0 && (
        <section className="panel">
          <h2>How methods compared</h2>
          <p className="muted tight">Lower score is better. Best plan is highlighted.</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Method</th>
                  <th>Score</th>
                  <th>Coverage %</th>
                  <th>Travel km</th>
                  <th>Fairness</th>
                  <th>Staffing %</th>
                  <th>Time (s)</th>
                </tr>
              </thead>
              <tbody>
                {ranking.map((r) => (
                  <tr
                    key={r.solver_id}
                    className={r.solver_id === bestId ? "best" : ""}
                  >
                    <td>
                      {METHOD_LABELS[r.solver_id] || r.solver_id}
                      {r.solver_id === bestId ? " ★" : ""}
                    </td>
                    <td>{r.objective_value == null ? "—" : fmt(r.objective_value)}</td>
                    <td>{fmt(r.population_coverage_pct, 1)}</td>
                    <td>{fmt(r.total_travel_km, 1)}</td>
                    <td>{fmt(r.gini_equity_index, 3)}</td>
                    <td>{fmt(r.who_compliance_pct, 1)}</td>
                    <td>{fmt(r.execution_time_sec, 2)}</td>
                  </tr>
                ))}
                {qres && (
                  <tr className="quantum-row">
                    <td>QAOA (quantum)</td>
                    <td>{fmt(qres.objective_value)}</td>
                    <td>{fmt(qres.population_coverage_pct, 1)}</td>
                    <td>{fmt(qres.total_travel_km, 1)}</td>
                    <td>{fmt(qres.gini_equity_index, 3)}</td>
                    <td>{fmt(qres.who_compliance_pct, 1)}</td>
                    <td>{fmt(qres.execution_time_sec, 2)}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {result.recommendations?.actionable_recommendations?.length > 0 && (
        <section className="panel">
          <h2>Deployment notes</h2>
          <ul className="recs">
            {result.recommendations.actionable_recommendations.slice(0, 5).map((rec, i) => (
              <li key={i}>{rec}</li>
            ))}
          </ul>
        </section>
      )}

      {sc.facilities?.length > 0 && (
        <section className="panel">
          <h2>Facility hubs (staff seats)</h2>
          <p className="muted tight">
            {staffedHubs.length} of {sc.facilities.length} hubs have at least one CHW seat.
            Highlighted rows are staffed.
          </p>
          <div className="table-wrap compact">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>CHW seats</th>
                </tr>
              </thead>
              <tbody>
                {sc.facilities.map((f) => (
                  <tr key={f.id} className={(f.available_chws || 0) > 0 ? "best" : ""}>
                    <td>{f.name}</td>
                    <td>{f.available_chws}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
