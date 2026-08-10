import type { ReactNode } from 'react';

import { PublicFooter, PublicNavigation, PublicSite } from './public-site';

export function LegalPage({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: ReactNode;
}) {
  return (
    <PublicSite>
      <PublicNavigation />
      <main className="legal-page">
        <article>
          <p className="eyebrow">Zylora legal</p>
          <h1>{title}</h1>
          <p className="legal-page__updated">Last updated: {updated}</p>
          {children}
        </article>
      </main>
      <PublicFooter />
    </PublicSite>
  );
}
