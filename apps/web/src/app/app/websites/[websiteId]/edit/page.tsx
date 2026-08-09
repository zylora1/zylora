import { WebsiteEditor } from '@/components/website-editor';

export default async function WebsiteEditorPage({
  params,
}: {
  params: Promise<{ websiteId: string }>;
}) {
  const { websiteId } = await params;
  return <WebsiteEditor websiteId={websiteId} />;
}
