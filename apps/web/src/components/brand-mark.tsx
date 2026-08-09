export function BrandMark({ admin = false, href }: { admin?: boolean; href?: string }) {
  return (
    <a
      className="brand-mark"
      href={href ?? (admin ? '/admin/login' : '/')}
      aria-label={admin ? 'Zylora Super Admin home' : 'Zylora home'}
    >
      <span aria-hidden="true" className="brand-glyph">
        Z
      </span>
      <span>Zylora{admin ? <small>Super Admin</small> : null}</span>
    </a>
  );
}
