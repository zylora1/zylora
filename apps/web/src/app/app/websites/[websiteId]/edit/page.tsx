import { PageManager } from '@/components/page-manager';

export default async function WebsiteEditorPage({
  params,
}: {
  params: Promise<{ websiteId: string }>;
}) {
  const { websiteId } = await params;
  return <PageManager websiteId={websiteId} />;
}
