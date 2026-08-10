import { LegalPage } from '@/components/legal-page';
export const metadata = { title: 'Privacy Policy' };
export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy" updated="August 2026">
      <h2>Information we use</h2>
      <p>
        Zylora uses account, Website, billing, support, and product activity data needed to provide
        the service. Sensitive fields remain behind authenticated service boundaries.
      </p>
      <h2>Your choices</h2>
      <p>
        Account privacy requests, marketing preferences, and export capabilities are available
        through the applicable product flows.
      </p>
    </LegalPage>
  );
}
