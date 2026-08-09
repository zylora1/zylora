import { BrandMark } from '@/components/brand-mark';

export default function HomePage() {
  return (
    <main className="home-shell">
      <nav className="home-nav">
        <BrandMark />
        <div className="home-actions">
          <a className="text-link" href="/login">
            Sign in
          </a>
          <a className="primary-link" href="/signup">
            Create account
          </a>
        </div>
      </nav>
      <section className="home-hero">
        <p className="eyebrow">Zylora · Websites with a point of view</p>
        <h1>A considered home for what you do.</h1>
        <p>
          Begin with a thoughtful foundation, shape it in your own voice, and publish when it feels
          right.
        </p>
        <a className="primary-link" href="/signup">
          Start with Zylora
        </a>
      </section>
    </main>
  );
}
