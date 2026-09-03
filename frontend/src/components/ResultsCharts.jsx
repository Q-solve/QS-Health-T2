import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const METHOD_LABELS = {
  c1_brute_force: "Exact (tiny)",
  c2_milp: "Exact / MILP",
  c3_greedy: "Nearest hub",
  c4_local_search: "Local search",
  c5_simulated_annealing: "Annealing",
  c6_genetic_algorithm: "Genetic",
  c7_tabu_search: "Tabu",
  qaoa_qbraid: "QAOA",
};

const CHART_COLORS = {
  score: "#3ecfb0",
  coverage: "#2bb673",
  travel: "#e9a23b",
  fairness: "#7aa2ff",
  demand: "#5ec8a8",
  walk: "#f0a56e",
};

function shortName(id) {
  return METHOD_LABELS[id] || id;
}

function ChartCard({ title, caption, children }) {
  return (
    <div className="chart-card card-block">
      <h3>{title}</h3>
      {caption && <p className="muted tight chart-caption">{caption}</p>}
      <div className="chart-box">{children}</div>
    </div>
  );
}

export default function ResultsCharts({ result }) {
  if (!result?.solved) return null;

  const ranking = result.classical?.ranking_by_objective || [];
  const bestId = result.classical?.best_classical;
  const best = bestId ? (result.classical?.results || {})[bestId] : null;
  const assignments = best?.assignments || [];
  const communities = result.scenario?.communities || [];
  const qres = result.quantum?.result;

  const methodRows = ranking
    .filter((r) => r.objective_value != null && Number(r.population_coverage_pct) > 0)
    .map((r) => ({
      method: shortName(r.solver_id),
      score: Number(r.objective_value) || 0,
      coverage: Number(r.population_coverage_pct) || 0,
      travel: Number(r.total_travel_km) || 0,
      fairness: Number(r.gini_equity_index) || 0,
      isBest: r.solver_id === bestId,
    }));
  if (qres && qres.objective_value != null) {
    methodRows.push({
      method: "QAOA",
      score: Number(qres.objective_value) || 0,
      coverage: Number(qres.population_coverage_pct) || 0,
      travel: Number(qres.total_travel_km) || 0,
      fairness: Number(qres.gini_equity_index) || 0,
      isBest: false,
    });
  }

  const walkRows = assignments
    .map((a) => ({
      name: (a.community_name || a.community_id || "?").slice(0, 18),
      walk: Number(a.walking_distance_km) || 0,
    }))
    .sort((a, b) => b.walk - a.walk)
    .slice(0, 12);

  const demandRows = [...communities]
    .map((c) => ({
      name: (c.name || c.id || "?").slice(0, 18),
      demand: Number(c.demand_score) || 0,
      population: Number(c.population) || 0,
    }))
    .sort((a, b) => b.demand - a.demand)
    .slice(0, 12);

  const sc = result.scenario || {};
  const factorCount = (sc.enabled_factors || []).length;

  if (!methodRows.length && !walkRows.length && !demandRows.length) return null;

  return (
    <section className="panel results-charts">
      <h2>Explainable results</h2>
      <p className="muted tight">
        Combined constraints (walk {sc.max_walking_dist_km} km · 1:{sc.who_ratio} people/CHW · fairness{" "}
        {sc.equity_target}) and {factorCount} need factors shaped this plan.
        {result.quantum?.skipped
          ? ` QAOA was not run: ${result.quantum.reason}`
          : result.quantum?.result
            ? " QAOA is the last bar on the method charts (same H(x) as classical)."
            : ""}
      </p>

      <div className="charts-grid">
        {methodRows.length > 0 && (
          <ChartCard
            title="Method comparison — objective score"
            caption="Lower is better. All methods optimize the same combined H(x): travel, staffing, fairness, and walk limits together."
          >
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={methodRows} margin={{ top: 8, right: 8, left: 0, bottom: 48 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2f574d" />
                <XAxis dataKey="method" tick={{ fill: "#9bb5ad", fontSize: 11 }} angle={-25} textAnchor="end" interval={0} />
                <YAxis tick={{ fill: "#9bb5ad", fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: "#16302b", border: "1px solid #2f574d", color: "#e8f2ef" }}
                />
                <Bar dataKey="score" name="Score H(x)" fill={CHART_COLORS.score} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        )}

        {methodRows.length > 0 && (
          <ChartCard
            title="Coverage vs fairness vs travel"
            caption="Higher coverage is better; lower fairness (Gini) and travel are better. Compare trade-offs across solvers."
          >
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={methodRows} margin={{ top: 8, right: 8, left: 0, bottom: 48 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2f574d" />
                <XAxis dataKey="method" tick={{ fill: "#9bb5ad", fontSize: 11 }} angle={-25} textAnchor="end" interval={0} />
                <YAxis tick={{ fill: "#9bb5ad", fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: "#16302b", border: "1px solid #2f574d", color: "#e8f2ef" }}
                />
                <Legend wrapperStyle={{ color: "#9bb5ad", fontSize: 12 }} />
                <Bar dataKey="coverage" name="Coverage %" fill={CHART_COLORS.coverage} radius={[3, 3, 0, 0]} />
                <Bar dataKey="travel" name="Travel km" fill={CHART_COLORS.travel} radius={[3, 3, 0, 0]} />
                <Bar dataKey="fairness" name="Gini" fill={CHART_COLORS.fairness} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        )}

        {demandRows.length > 0 && (
          <ChartCard
            title="Community need (combined factors)"
            caption="Demand score (0–1) is the equal-weight mix of your selected unified-dataset factors × population mix."
          >
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={demandRows} layout="vertical" margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2f574d" />
                <XAxis type="number" domain={[0, 1]} tick={{ fill: "#9bb5ad", fontSize: 11 }} />
                <YAxis type="category" dataKey="name" width={100} tick={{ fill: "#9bb5ad", fontSize: 10 }} />
                <Tooltip
                  contentStyle={{ background: "#16302b", border: "1px solid #2f574d", color: "#e8f2ef" }}
                  formatter={(v, _n, props) => [`${Number(v).toFixed(3)} (pop ${props.payload.population})`, "Demand"]}
                />
                <Bar dataKey="demand" name="Demand" fill={CHART_COLORS.demand} radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        )}

        {walkRows.length > 0 && (
          <ChartCard
            title="Walking distance by community"
            caption="Assigned hub walk in km for the best plan. Bars above your walk limit indicate soft walk-cap pressure."
          >
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={walkRows} layout="vertical" margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2f574d" />
                <XAxis type="number" tick={{ fill: "#9bb5ad", fontSize: 11 }} />
                <YAxis type="category" dataKey="name" width={100} tick={{ fill: "#9bb5ad", fontSize: 10 }} />
                <Tooltip
                  contentStyle={{ background: "#16302b", border: "1px solid #2f574d", color: "#e8f2ef" }}
                  formatter={(v) => [`${Number(v).toFixed(1)} km`, "Walk"]}
                />
                <Bar dataKey="walk" name="Walk km" fill={CHART_COLORS.walk} radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        )}
      </div>
    </section>
  );
}
