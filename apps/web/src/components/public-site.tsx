import Link from 'next/link';
import type { ReactNode } from 'react';

import { BrandMark } from './brand-mark';
import styles from './public-site.module.css';

export function PublicSite({ children }: { children: ReactNode }) {
  return <div className={styles.site}>{children}</div>;
}

export function PublicNavigation() {
  return (
    <header className={styles.header}>
      <nav className={styles.navigation} aria-label="Primary navigation">
        <BrandMark />
        <div className={styles.links}>
          <Link href="/templates">Templates</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/blog">Journal</Link>
          <Link href="/contact">Contact</Link>
        </div>
        <div className={styles.actions}>
          <Link href="/login">Sign in</Link>
          <Link className={styles.cta} href="/signup">
            Start building
          </Link>
        </div>
      </nav>
    </header>
  );
}

export function PublicFooter() {
  return (
    <footer className={styles.footer}>
      <div>
        <BrandMark />
        <p>Thoughtful Website creation, ownership, and publishing in one clear portal.</p>
      </div>
      <nav aria-label="Footer navigation">
        <Link href="/templates">Templates</Link>
        <Link href="/pricing">Pricing</Link>
        <Link href="/blog">Journal</Link>
        <Link href="/contact">Contact</Link>
      </nav>
      <nav aria-label="Legal navigation">
        <Link href="/privacy">Privacy</Link>
        <Link href="/terms">Terms</Link>
        <Link href="/cookies">Cookies</Link>
        <Link href="/refunds">Refunds & cancellations</Link>
      </nav>
    </footer>
  );
}
