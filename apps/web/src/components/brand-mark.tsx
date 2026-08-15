export function BrandMark({ admin = false, href }: { admin?: boolean; href?: string }) {
  return (
    <a
      className="brand-mark"
      href={href ?? (admin ? '/admin/login' : '/')}
      aria-label={admin ? 'Zylora Super Admin home' : 'Zylora home'}
    >
      <svg aria-hidden="true" className="brand-glyph" viewBox="0 0 64 64" fill="none">
        <path d="M14 16h36L18 48h32" />
        <path className="brand-glyph__accent" d="M39 16h11v11" />
      </svg>
      <span className="brand-wordmark">Zylora{admin ? <small>Super Admin</small> : null}</span>
    </a>
  );
}
