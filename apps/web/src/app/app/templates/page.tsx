import { PageHeader } from '@zylora/ui';

import { TemplateGallery } from '@/components/template-gallery';

export default function UserTemplatesPage() {
  return (
    <div className="workspace-page">
      <PageHeader
        eyebrow="Approved catalogue"
        title="Choose your starting point"
        description="Select a current, validated Template to create its complete private multi-page Draft. No business questionnaire, plan, payment, or publishing limit applies here."
      />
      <TemplateGallery createDraft />
    </div>
  );
}
