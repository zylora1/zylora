import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { PublicFooter, PublicNavigation, PublicSite } from '@/components/public-site';
import { TemplateDetail } from '@/components/template-detail';
import styles from '@/components/template-platform.module.css';

type TemplateMetadata = {
  slug: string;
  name: string;
  summary: string;
  category: string;
};

export const dynamic = 'force-dynamic';

async function templateMetadata(
  slug: string,
): Promise<{ item: TemplateMetadata | null; missing: boolean }> {
  const api = process.env.API_INTERNAL_URL ?? 'http://127.0.0.1:8000';
  try {
    const response = await fetch(`${api}/api/v1/templates/${encodeURIComponent(slug)}`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(2_500),
    });
    if (response.status === 404) return { item: null, missing: true };
    if (!response.ok) return { item: null, missing: false };
    return { item: (await response.json()) as TemplateMetadata, missing: false };
  } catch {
    return { item: null, missing: false };
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { item } = await templateMetadata((await params).slug);
  if (!item) return { title: 'Template unavailable', robots: { index: false, follow: false } };
  return {
    title: `${item.name} Website Template`,
    description: item.summary,
    alternates: { canonical: `/templates/${item.slug}` },
    openGraph: {
      title: `${item.name} Website Template`,
      description: item.summary,
    },
  };
}

export default async function TemplatePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const result = await templateMetadata(slug);
  if (result.missing) notFound();
  const item = result.item;
  const schema = item
    ? JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        name: `${item.name} Website Template`,
        description: item.summary,
        url: `/templates/${item.slug}`,
        breadcrumb: {
          '@type': 'BreadcrumbList',
          itemListElement: [
            { '@type': 'ListItem', position: 1, name: 'Home', item: '/' },
            { '@type': 'ListItem', position: 2, name: 'Templates', item: '/templates' },
            { '@type': 'ListItem', position: 3, name: item.name, item: `/templates/${item.slug}` },
          ],
        },
      }).replace(/</g, '\\u003c')
    : null;
  return (
    <PublicSite>
      <PublicNavigation />
      <div className={styles.catalogPage}>
        <main className={styles.catalogMain}>
          {schema ? (
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: schema }} />
          ) : null}
          <TemplateDetail slug={slug} />
        </main>
      </div>
      <PublicFooter />
    </PublicSite>
  );
}
