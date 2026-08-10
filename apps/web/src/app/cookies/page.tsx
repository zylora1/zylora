import { LegalPage } from '@/components/legal-page';
export const metadata = { title: 'Cookie Policy' };
export default function CookiesPage() {
  return (
    <LegalPage title="Cookie Policy" updated="August 2026">
      <h2>Essential cookies</h2>
      <p>
        Zylora uses secure session and CSRF cookies needed to authenticate Users and protect
        requests. These cookies are not used to grant capability from browser state.
      </p>
      <h2>Preference and analytics data</h2>
      <p>
        Where product analytics are enabled, they use the published Website context and privacy-safe
        identifiers described in the product.
      </p>
    </LegalPage>
  );
}
