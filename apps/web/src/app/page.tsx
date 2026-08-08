const foundations = [
  'Next.js application boundary',
  'FastAPI service contract',
  'PostgreSQL migration path',
  'Redis-backed worker transport',
] as const;

export default function FoundationPage() {
  return (
    <main className="foundation-shell">
      <section aria-labelledby="foundation-title" className="foundation-panel">
        <p className="eyebrow">Zylora V2 · Phase 1</p>
        <h1 id="foundation-title">Platform foundation</h1>
        <p className="summary">
          This environment exposes the verified application boundaries. Product workflows begin in
          their owning phases after this foundation passes its quality gates.
        </p>
        <ul aria-label="Foundation components">
          {foundations.map((foundation) => (
            <li key={foundation}>{foundation}</li>
          ))}
        </ul>
      </section>
    </main>
  );
}
