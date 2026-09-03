import React from "react";

const EVIDENCE_LABEL = {
  candidate: "Candidate",
  aspirational: "Aspirational",
  not_applicable: "Not applicable",
  demonstrated_workflow: "Workflow demonstrated",
  roadmap: "Roadmap",
};

const PRIORITY_CLASS = {
  high: "prio-high",
  medium: "prio-med",
  low: "prio-low",
};

export default function ClassicalEvaluationPanel({ evaluation }) {
  if (!evaluation) {
    return (
      <section className="panel">
        <h2>Classical ranking &amp; quantum opportunities</h2>
        <p className="muted">Loading evaluation from published benchmarks…</p>
      </section>
    );
  }

  if (evaluation.status === "missing_classical") {
    return (
      <section className="panel">
        <h2>Classical ranking &amp; quantum opportunities</h2>
        <p className="muted">Publish classical suite results first, then refresh.</p>
      </section>
    );
  }

  const solvers = evaluation.classical_ranking?.solvers || [];
  const opportunities = evaluation.failure_to_quantum?.opportunities || [];
  const headline = evaluation.headline || {};
  const metric = evaluation.classical_ranking?.ranking_metric;

  return (
    <section className="panel eval-panel">
      <h2>Classical ranking &amp; where quantum can add value</h2>
      <p className="muted tight">
        {headline.message || evaluation.failure_to_quantum?.framing}
      </p>

      <div className="stat-row">
        <div className="stat">
          <span className="stat-val">{headline.top_operational_name || headline.top_classical_name || "—"}</span>
          <span className="stat-lab">Top operational</span>
        </div>
        <div className="stat">
          <span className="stat-val">{evaluation.classical_ranking?.n_instances ?? "—"}</span>
          <span className="stat-lab">Instances ranked</span>
        </div>
        <div className="stat">
          <span className="stat-val">{headline.qaoa_strictly_better ?? 0}</span>
          <span className="stat-lab">QAOA beats best</span>
        </div>
        <div className="stat">
          <span className="stat-val">{headline.quantum_needed_candidates ?? 0}</span>
          <span className="stat-lab">Quantum-needed candidates</span>
        </div>
      </div>
      {headline.top_classical_name && headline.top_classical !== headline.top_operational && (
        <p className="muted tight">
          Exact oracle on tiny graphs: {headline.top_classical_name}. Operational ranking for C2–C7
          leads with {headline.top_operational_name}.
        </p>
      )}

      <h3 className="eval-subhead">Classical algorithm ranking</h3>
      {metric && <p className="muted tight chart-caption">{metric}</p>}
      <div className="table-wrap compact">
        <table>
          <thead>
            <tr>
              <th>Op#</th>
              <th>Solver</th>
              <th>Near-best</th>
              <th>Exclusive wins</th>
              <th>Usable</th>
              <th>Med. gap</th>
              <th>Med. time</th>
              <th>Fail rate</th>
              <th>Score</th>
            </tr>
          </thead>
          <tbody>
            {[...solvers]
              .sort((a, b) => (a.operational_rank ?? 99) - (b.operational_rank ?? 99) || a.rank - b.rank)
              .map((s) => (
              <tr
                key={s.solver_id}
                className={s.operational_rank === 1 || (s.operational_rank == null && s.rank === 1) ? "best" : undefined}
              >
                <td>{s.operational_rank ?? "—"}</td>
                <td>
                  <div className="solver-cell">
                    <strong>{s.name}</strong>
                    <span className="solver-role">{s.role}</span>
                  </div>
                </td>
                <td>{((s.near_best_rate || 0) * 100).toFixed(0)}%</td>
                <td>{s.exclusive_wins}</td>
                <td>{((s.usable_rate || 0) * 100).toFixed(0)}%</td>
                <td>
                  {s.median_gap_to_best == null ? "—" : Number(s.median_gap_to_best).toFixed(3)}
                </td>
                <td>
                  {s.median_time_sec == null ? "—" : `${Number(s.median_time_sec).toFixed(3)}s`}
                </td>
                <td>{((s.fail_rate || 0) * 100).toFixed(0)}%</td>
                <td>{Number(s.composite_score).toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className="eval-subhead">Classical limits → quantum opportunity</h3>
      <p className="muted tight">
        Even when classical already solves an instance, quantum can still add ensemble sampling,
        hybrid partition search, or fair NISQ evidence — without claiming full replacement.
      </p>

      <div className="opportunity-grid">
        {opportunities.map((op) => (
          <article key={op.id} className={`opportunity-card ${PRIORITY_CLASS[op.priority] || ""}`}>
            <header className="opportunity-head">
              <span className="opportunity-id">{op.id}</span>
              <span className={`evidence-pill ${op.evidence_status}`}>
                {EVIDENCE_LABEL[op.evidence_status] || op.evidence_status}
              </span>
            </header>
            <p className="opportunity-fail">
              <strong>Classical limit:</strong> {op.classical_failure}
            </p>
            <p className="opportunity-obs">
              Observed: <strong>{op.observed_instances}</strong>
              {op.priority ? ` · priority ${op.priority}` : ""}
            </p>
            <p className="opportunity-still">
              <strong>When classical still works:</strong> {op.when_classical_still_works}
            </p>
            <p className="opportunity-add">
              <strong>Quantum can add:</strong> {op.quantum_can_add}
            </p>
            <p className="opportunity-caveat muted tight">{op.not_a_claim}</p>
          </article>
        ))}
      </div>

      {evaluation.qml_vs_classical?.verdict_note && (
        <p className="muted tight qml-note">
          Demand QML: {evaluation.qml_vs_classical.verdict_note}
        </p>
      )}
    </section>
  );
}
