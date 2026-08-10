import type { Metadata } from 'next';

import { BlogIndex } from '@/components/public-blog';

export const metadata: Metadata = {
  title: 'Journal',
  description: 'Practical notes on shaping, publishing, and improving a Website you own.',
  alternates: { canonical: '/blog' },
};

export default function BlogPage() {
  return <BlogIndex />;
}
