export default function VerdictBanner({ verdict }) {
  if (!verdict) return null;
  const ready = verdict.status === "ready";
  const line = ready
    ? verdict.summary_line || "Verdict ready"
    : verdict.note || "Verdict not yet computed — run scripts/write_advantage_verdict.py";

  return (
    <aside className={`verdict-banner ${ready ? "ready" : "pending"}`} role="status">
      <div className="verdict-label">Advantage verdict</div>
      <p className="verdict-text">{line}</p>
      {ready && verdict.path && (
        <p className="verdict-path">Source: {verdict.path}</p>
      )}
    </aside>
  );
}
