import type { Metadata } from 'next';
import Link from 'next/link';

import { TemplateGallery } from '@/components/template-gallery';
import styles from '@/components/template-platform.module.css';

export const metadata: Metadata = {
  title: 'Approved website Templates',
  description: 'Browse validated, approved Zylora Templates and preview every design responsively.',
};

export default function TemplatesPage() {
  return (
    <div className={styles.catalogPage}>
      <nav className={styles.publicNav} aria-label="Public">
        <Link href="/">Zylora</Link>
        <div>
          <Link href="/templates">Templates</Link>
          <Link href="/login">Sign in</Link>
        </div>
      </nav>
      <main className={styles.catalogMain}>
        <header className={styles.catalogHero}>
          <h1>A strong starting point.</h1>
          <p>
            Every Template is structured, responsive, validated, and approved before it appears
            here. Explore by fit, then inspect the real design at desktop, tablet, and mobile
            widths.
          </p>
        </header>
        <TemplateGallery />
      </main>
    </div>
  );
}
