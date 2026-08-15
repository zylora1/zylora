import Link from 'next/link';

import { PublicFooter, PublicNavigation, PublicSite } from '@/components/public-site';

export default function NotFound() {
  return (
    <PublicSite>
      <PublicNavigation />
      <main className="not-found-page">
        <p className="eyebrow">404 / Page not found</p>
        <h1>That path does not lead to a Zylora page.</h1>
        <p>
          It may have moved, or the address may not be complete. Start again from a place we know.
        </p>
        <Link href="/" className="not-found-page__action">
          Back home
        </Link>
      </main>
      <PublicFooter />
    </PublicSite>
  );
}
