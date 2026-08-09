export function BrandMark({ admin = false }: { admin?: boolean }) {
  return (
    <a className="brand-mark" href={admin ? '/admin/login' : '/'} aria-label="Zylora home">
      <span aria-hidden="true" className="brand-glyph">
        Z
      </span>
      <span>
        Zylora
        {admin ? <small>Super Admin</small> : null}
      </span>
    </a>
  );
}
