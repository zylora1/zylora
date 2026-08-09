import { PageHeader } from '@zylora/ui';

import { TemplateManagement } from '@/components/template-management';

export default function AdminTemplatesPage() {
  return (
    <div className="workspace-page">
      <PageHeader
        eyebrow="Super Admin"
        title="Template lifecycle"
        description="Create stable Template identities, import immutable structured versions, then validate, approve, publish, or deprecate with an audited reason."
      />
      <TemplateManagement />
    </div>
  );
}
