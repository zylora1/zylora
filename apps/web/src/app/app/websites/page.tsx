import { PageHeader } from '@zylora/ui';

import { WebsiteDrafts } from '@/components/website-drafts';

export default function WebsitesPage() {
  return (
    <div className="workspace-page">
      <PageHeader
        eyebrow="Your Websites"
        title="Draft projects"
        description="Own multiple private Drafts in one Zylora portal. Each Draft has one owner and a complete independent Page structure."
      />
      <WebsiteDrafts />
    </div>
  );
}
