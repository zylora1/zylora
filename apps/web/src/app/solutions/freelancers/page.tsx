import type { Metadata } from 'next';

import { SearchLandingPage, type SearchLandingContent } from '@/components/search-landing';
import { absoluteUrl, createPageMetadata, serializeJsonLd } from '@/lib/seo';

const path = '/solutions/freelancers';
const content = {
  eyebrow: 'Website builder for freelancers',
  title: 'Build client Websites without inventing a second ownership model.',
  intro:
    'Use one User account to manage multiple private drafts, start from an approved Template or Zylora AI, preview the work, then transfer the Website to its next owner or purchase an eligible deployable export.',
  proof:
    'Freelancing is a delivery workflow in Zylora, not a third account role. Every Website always has exactly one current owner, and ownership changes are transactional and audited.',
  path,
  primaryCta: { label: 'Start a client Website', href: '/signup' },
  secondaryCta: { label: 'Explore Website Templates', href: '/templates' },
  breadcrumbs: [{ label: 'Independent professionals', href: path }],
  sections: [
    {
      label: 'PIPELINE',
      title: 'Keep multiple client drafts organized under one User account.',
      copy: 'Create and manage multiple private Website drafts while the one-live-Website rule remains explicit for the current owner.',
      points: [
        'Multiple owned drafts',
        'Clear Website status',
        'No invented specialist account role',
      ],
    },
    {
      label: 'CREATION',
      title: 'Match the starting method to the client engagement.',
      copy: 'Choose a validated Template when the direction is known, or use the durable AI generation workflow for a more specific business brief.',
      points: [
        'Template-first control',
        'AI-generated Next.js path',
        'Responsive preview before delivery',
      ],
    },
    {
      label: 'HANDOFF',
      title: 'Transfer the Website, not a copied shadow record.',
      copy: 'The recipient becomes the single current owner through a transactional transfer. The ownership history remains auditable and the Website stays the same aggregate.',
      points: [
        'Exactly one current owner',
        'Transactional transfer',
        'Recipient uses a Zylora User account',
      ],
    },
    {
      label: 'EXPORT',
      title: 'Use the paid Website export only when it is the right delivery path.',
      copy: 'An eligible deployable ZIP is a separate paid product flow. It is not the same as an account privacy export and cannot be unlocked by frontend state.',
      points: ['Separate purchase record', 'Immutable export artifact', 'No privacy-export bypass'],
    },
  ],
  steps: [
    {
      number: '01',
      title: 'Create',
      copy: 'Choose a Template or start a Zylora AI project for the client brief.',
    },
    { number: '02', title: 'Shape', copy: 'Edit, preview, and recover the private Website work.' },
    {
      number: '03',
      title: 'Approve',
      copy: 'Review the responsive result and decide on publish, transfer, or export.',
    },
    {
      number: '04',
      title: 'Deliver',
      copy: 'Transfer ownership transactionally or complete the separate eligible export purchase.',
    },
  ],
  related: [
    {
      label: 'Website Templates',
      href: '/templates',
      copy: 'Browse approved foundations for different client needs.',
    },
    {
      label: 'Zylora Features',
      href: '/features',
      copy: 'Review editing, publishing, domains, Leads, transfer, and export.',
    },
    {
      label: 'Pricing',
      href: '/pricing',
      copy: 'See current publishing plans and separate export information.',
    },
  ],
} satisfies SearchLandingContent;

export const metadata: Metadata = createPageMetadata({
  title: 'Website Builder for Independent Professionals',
  description:
    'Build client Websites from Templates or with AI, manage private drafts, preview responsively, then transfer ownership or purchase an eligible export.',
  path,
});

const schema = serializeJsonLd({
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'WebPage',
      name: 'Website Builder for Independent Professionals',
      description: metadata.description,
      url: absoluteUrl(path),
    },
    {
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'Home', item: absoluteUrl('/') },
        {
          '@type': 'ListItem',
          position: 2,
          name: 'Independent professionals',
          item: absoluteUrl(path),
        },
      ],
    },
  ],
});

export default function FreelancersPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: schema }} />
      <SearchLandingPage content={content} />
    </>
  );
}
