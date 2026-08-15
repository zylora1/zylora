'use client';

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          background: '#f4f5ef',
          color: '#17211f',
          fontFamily: 'Segoe UI, Arial, sans-serif',
        }}
      >
        <main
          style={{ display: 'grid', minHeight: '100vh', placeItems: 'center', padding: '1.5rem' }}
        >
          <section
            style={{
              maxWidth: '34rem',
              border: '1px solid #d8ddd4',
              borderRadius: '1rem',
              background: '#fffefa',
              padding: '2rem',
            }}
          >
            <p
              style={{
                margin: 0,
                color: '#d66d4a',
                fontSize: '0.72rem',
                fontWeight: 800,
                letterSpacing: '0.12em',
              }}
            >
              ZYLORA / RECOVERY
            </p>
            <h1
              style={{
                margin: '0.75rem 0',
                fontFamily: 'Georgia, serif',
                fontSize: '2.5rem',
                letterSpacing: '-0.06em',
              }}
            >
              We need to reset this view.
            </h1>
            <p style={{ color: '#65716c', lineHeight: 1.6 }}>
              No account or Website data has been changed. Retry safely to return to Zylora.
            </p>
            <button
              type="button"
              onClick={reset}
              style={{
                minHeight: '2.75rem',
                border: 0,
                borderRadius: '0.65rem',
                background: '#173a36',
                color: '#fff',
                padding: '0.65rem 0.9rem',
                fontWeight: 800,
              }}
            >
              Try again
            </button>
          </section>
        </main>
      </body>
    </html>
  );
}
