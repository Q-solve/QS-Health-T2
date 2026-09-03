export default function SharedBenchmarkPanel({ shared, paired }) {
  if (!shared) {
    return (
      <section className="panel">
        <h2>Shared instances</h2>
        <p className="muted">Loading classical ↔ quantum catalogue…</p>
      </section>
    );
  }

  return (
    <section className="panel">
      <h2>Shared classical ↔ quantum instances</h2>
      <p className="muted tight">
        Joined on (tier, county, seed, constraint, feature_stage) so both solvers see the same ladder graph.
      </p>
      <div className="stat-row">
        <div className="stat">
          <span className="stat-val">{shared.instances_both ?? 0}</span>
          <span className="stat-lab">Both</span>
        </div>
        <div className="stat">
          <span className="stat-val">{shared.instances_classical_only ?? 0}</span>
          <span className="stat-lab">Classical only</span>
        </div>
        <div className="stat">
          <span className="stat-val">{shared.instances_quantum_only ?? 0}</span>
          <span className="stat-lab">Quantum only</span>
        </div>
        <div className="stat">
          <span className="stat-val">
            {shared.preliminary_advantage_signals?.qaoa_strictly_better_than_best_classical ?? 0}
          </span>
          <span className="stat-lab">QAOA beats best</span>
        </div>
      </div>

      <div className="table-wrap compact">
        <table>
          <thead>
            <tr>
              <th>Tier</th>
              <th>County</th>
              <th>Seed</th>
              <th>N</th>
              <th>Best classical</th>
              <th>QAOA H(x)</th>
              <th>Gap</th>
              <th>Beats?</th>
            </tr>
          </thead>
          <tbody>
            {(paired?.rows || shared.instances?.filter((i) => i.presence === "both") || [])
              .slice(0, 24)
              .map((row) => (
                <tr key={`${row.tier}-${row.county}-${row.seed}-${row.constraint_setting}-${row.feature_stage}`}>
                  <td>{row.tier}</td>
                  <td>{row.county}</td>
                  <td>{row.seed}</td>
                  <td>{row.num_variables ?? "—"}</td>
                  <td>
                    {row.best_classical
                      ? `${row.best_classical.solver_id} (${Number(row.best_classical.objective_value).toFixed(1)})`
                      : "—"}
                  </td>
                  <td>
                    {row.quantum?.objective_value != null
                      ? Number(row.quantum.objective_value).toFixed(1)
                      : "—"}
                  </td>
                  <td>
                    {row.quantum?.gap_to_best_classical != null
                      ? Number(row.quantum.gap_to_best_classical).toFixed(3)
                      : "—"}
                  </td>
                  <td>{row.quantum?.beats_best_classical ? "yes" : "no"}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
