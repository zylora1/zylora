import type { Metadata } from 'next';

import { TemplateGallery } from '@/components/template-gallery';
import { PublicFooter, PublicNavigation, PublicSite } from '@/components/public-site';
import styles from '@/components/template-platform.module.css';

export const metadata: Metadata = {
  title: 'Website Templates',
  description: 'Browse validated, approved Zylora Templates and preview every design responsively.',
  alternates: { canonical: '/templates' },
  openGraph: {
    title: 'Zylora Website Templates',
    description: 'Validated, approved Templates for a thoughtful Website starting point.',
  },
};

export default function TemplatesPage() {
  return (
    <PublicSite>
      <PublicNavigation />
      <div className={styles.catalogPage}>
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
      <PublicFooter />
    </PublicSite>
  );
}
