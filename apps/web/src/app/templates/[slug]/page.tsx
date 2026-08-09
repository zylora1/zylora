import type { Metadata } from 'next';
import Link from 'next/link';

import { TemplateDetail } from '@/components/template-detail';
import styles from '@/components/template-platform.module.css';

export const metadata: Metadata = { title: 'Template details' };
export default async function TemplatePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return (
    <div className={styles.catalogPage}>
      <nav className={styles.publicNav}>
        <Link href="/">Zylora</Link>
        <Link href="/templates">All Templates</Link>
      </nav>
      <main className={styles.catalogMain}>
        <TemplateDetail slug={slug} />
      </main>
    </div>
  );
}
