import {
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

const COLORS = [
  "#0d7377",
  "#14919b",
  "#2a9d8f",
  "#e76f51",
  "#f4a261",
  "#264653",
  "#6d597a",
];

export default function ScalingChart({ records }) {
  const usable = (records || []).filter(
    (r) => r.objective_value != null && r.num_variables != null && r.execution_time_sec != null
  );
  const bySolver = {};
  for (const r of usable) {
    const sid = r.solver_id || "unknown";
    (bySolver[sid] ||= []).push({
      n: r.num_variables,
      time: r.execution_time_sec,
      h: r.objective_value,
      county: r.county,
      tier: r.tier,
    });
  }
  const solvers = Object.keys(bySolver).sort();

  if (!solvers.length) {
    return (
      <section className="panel">
        <h2>Scaling</h2>
        <p className="muted">No classical suite records yet. Run scripts/run_classical_suite.py.</p>
      </section>
    );
  }

  return (
    <section className="panel">
      <h2>Classical scaling (runtime vs N)</h2>
      <p className="muted tight">Wall-clock seconds vs N = F × C from published suite results.</p>
      <div className="chart-box">
        <ResponsiveContainer width="100%" height={320}>
          <ScatterChart margin={{ top: 8, right: 12, bottom: 8, left: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#c5d0ce" />
            <XAxis
              type="number"
              dataKey="n"
              name="N"
              tick={{ fontSize: 11 }}
              label={{ value: "N = F×C", position: "insideBottom", offset: -2, fontSize: 11 }}
            />
            <YAxis
              type="number"
              dataKey="time"
              name="time"
              scale="log"
              domain={["auto", "auto"]}
              tick={{ fontSize: 11 }}
              label={{ value: "Time (s)", angle: -90, position: "insideLeft", fontSize: 11 }}
            />
            <ZAxis range={[40, 40]} />
            <Tooltip
              cursor={{ strokeDasharray: "3 3" }}
              formatter={(v, name) => [typeof v === "number" ? v.toFixed(3) : v, name]}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {solvers.map((sid, i) => (
              <Scatter
                key={sid}
                name={sid.replace(/^c\d_/, "").slice(0, 18)}
                data={bySolver[sid]}
                fill={COLORS[i % COLORS.length]}
              />
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
