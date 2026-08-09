import { notFound } from 'next/navigation';

import { findSection, userSections } from '@/components/portal-navigation';
import { UserSectionPage } from '@/components/portal-pages';

export function generateStaticParams() {
  return userSections.map(({ slug }) => ({ section: slug }));
}

export default async function SectionPage({ params }: { params: Promise<{ section: string }> }) {
  const section = findSection(userSections, (await params).section);
  if (!section) notFound();
  return <UserSectionPage section={section} />;
}
