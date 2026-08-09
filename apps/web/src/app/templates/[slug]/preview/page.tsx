import type { Metadata } from 'next';

import { TemplatePreview } from '@/components/template-preview';

export const metadata: Metadata = {
  title: 'Responsive Template preview',
  robots: { index: false, follow: false },
};
export default async function PreviewPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ version?: string }>;
}) {
  const { slug } = await params;
  const version = Number((await searchParams).version || 1);
  return (
    <TemplatePreview
      slug={slug}
      version={version}
      name={slug
        .split('-')
        .map((value) => value[0]?.toUpperCase() + value.slice(1))
        .join(' ')}
    />
  );
}
