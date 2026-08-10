import type { Metadata } from 'next';

import { PricingCatalog } from '@/components/pricing-catalog';

export const metadata: Metadata = {
  title: 'Pricing',
  description: 'Compare Zylora publishing plans and the product capabilities they unlock.',
  alternates: { canonical: '/pricing' },
};

export default function PricingPage() {
  return <PricingCatalog />;
}
