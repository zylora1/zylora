import type { Metadata } from 'next';

import { AiBuilderProject } from '@/components/ai-builder-project';

export const metadata: Metadata = {
  title: 'Build with AI',
  description: 'Describe a business website and queue an isolated Zylora AI production build.',
  robots: { index: false, follow: false },
};

export default function AiBuilderPage() {
  return <AiBuilderProject />;
}
