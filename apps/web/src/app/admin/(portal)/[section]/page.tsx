import { notFound } from 'next/navigation';

import { adminSections, findSection } from '@/components/portal-navigation';
import { AdminSectionPage } from '@/components/portal-pages';

export function generateStaticParams() {
  return adminSections.map(({ slug }) => ({ section: slug }));
}

export default async function AdminSection({ params }: { params: Promise<{ section: string }> }) {
  const section = findSection(adminSections, (await params).section);
  if (!section) notFound();
  return <AdminSectionPage section={section} />;
}
