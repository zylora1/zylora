import { LegalPage } from '@/components/legal-page';
export const metadata = { title: 'Refunds and cancellations' };
export default function RefundsPage() {
  return (
    <LegalPage title="Refunds and cancellations" updated="August 2026">
      <h2>Subscriptions</h2>
      <p>
        Cancellation and refund availability depend on the applicable purchase flow, provider terms,
        and law. Cancelling never silently deletes your Website content.
      </p>
      <h2>Help with a charge</h2>
      <p>
        Contact support with the billing email, purchase reference, and a concise description of the
        issue. We will review the request using the applicable records and policy.
      </p>
    </LegalPage>
  );
}
