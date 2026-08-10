import { LegalPage } from '@/components/legal-page';
export const metadata = { title: 'Terms of Service' };
export default function TermsPage() {
  return (
    <LegalPage title="Terms of Service" updated="August 2026">
      <h2>Using Zylora</h2>
      <p>
        You are responsible for content you publish and for ensuring that you have the rights to use
        it. Zylora provides structured Website creation and related product capabilities subject to
        your active entitlement.
      </p>
      <h2>Service changes</h2>
      <p>
        Availability, provider integration, and plan entitlements are governed by the applicable
        product and purchase terms.
      </p>
    </LegalPage>
  );
}
