function fmtH(v) {
  if (v == null || Number.isNaN(Number(v))) return "—";
  const n = Number(v);
  if (Math.abs(n) >= 1e6) return n.toExponential(3);
  if (Math.abs(n) >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 1 });
  return n.toFixed(3);
}

function fmtGap(v) {
  if (v == null || Number.isNaN(Number(v))) return "—";
  return Number(v).toFixed(3);
}

function winnerLabel(w) {
  if (w === "tie") return "tie";
  if (w === "classical") return "classical";
  if (w === "quantum") return "quantum";
  return "—";
}

export default function ObjectiveCompareTable({ compare }) {
  if (!compare) {
    return (
      <section className="panel">
        <h2>Objective H(x): classical vs quantum</h2>
        <p className="muted">Loading optimised objective values from published benchmarks…</p>
      </section>
    );
  }

  const rows = compare.rows || [];
  const summary = compare.summary || {};

  return (
    <section className="panel">
      <h2>Objective H(x): classical vs quantum</h2>
      <p className="muted tight">
        Shared objective values from{" "}
        <code>{compare.source || "data/quantum_benchmark_results.json"}</code>. Lower H(x) is better.
        Classical column uses the best usable classical run on the same instance.
      </p>

      <div className="stat-row">
        <div className="stat">
          <span className="stat-val">{compare.n ?? rows.length}</span>
          <span className="stat-lab">Instances</span>
        </div>
        <div className="stat">
          <span className="stat-val">{summary.classical_lower_H ?? 0}</span>
          <span className="stat-lab">Classical lower H</span>
        </div>
        <div className="stat">
          <span className="stat-val">{summary.tie ?? 0}</span>
          <span className="stat-lab">Tie</span>
        </div>
        <div className="stat">
          <span className="stat-val">{summary.quantum_lower_H ?? 0}</span>
          <span className="stat-lab">Quantum lower H</span>
        </div>
      </div>

      <div className="table-wrap compact">
        <table>
          <thead>
            <tr>
              <th>Tier</th>
              <th>County</th>
              <th>N</th>
              <th>Classical solver</th>
              <th>Classical H(x)</th>
              <th>Quantum H(x)</th>
              <th>Gap (Q−C)/|C|</th>
              <th>Lower H</th>
              <th>Q status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const win = row.lower_H_wins;
              const rowClass =
                win === "quantum" ? "quantum-row" : win === "classical" || win === "tie" ? "best" : undefined;
              return (
                <tr
                  key={`${row.tier}-${row.county}-${row.seed}-${row.constraint_setting}-${row.feature_stage}`}
                  className={rowClass}
                >
                  <td>{row.tier}</td>
                  <td>{row.county}</td>
                  <td>{row.num_variables ?? "—"}</td>
                  <td>{row.classical_solver || "—"}</td>
                  <td>{fmtH(row.classical_H)}</td>
                  <td>{fmtH(row.quantum_H)}</td>
                  <td>{fmtGap(row.gap_qaoa_to_classical)}</td>
                  <td>{winnerLabel(win)}</td>
                  <td>{row.quantum_status || "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
