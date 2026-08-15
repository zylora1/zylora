import type { Metadata } from 'next';

import { SearchLandingPage, type SearchLandingContent } from '@/components/search-landing';
import { absoluteUrl, createPageMetadata, serializeJsonLd } from '@/lib/seo';

const content = {
  eyebrow: 'Zylora product features',
  title: 'The complete path from first draft to a working business website.',
  intro:
    'Zylora brings Template discovery, AI generation, structured editing, publishing, custom domains, Lead capture, ownership transfer, and eligible export into one product with clear server-authoritative boundaries.',
  proof:
    'Features do not become available because a button is visible or a query parameter says so. Plans, ownership, publishing requirements, and paid actions are evaluated by canonical backend services.',
  path: '/features',
  primaryCta: { label: 'Start building', href: '/signup' },
  secondaryCta: { label: 'View Website Templates', href: '/templates' },
  sections: [
    {
      label: 'CREATE',
      title: 'Template-first or generated with AI.',
      copy: 'Choose an approved Template for a known foundation, or describe the business and follow the durable Zylora AI generation path.',
      points: [
        '1,000+ prepared starting points',
        'AI requirements and build workflow',
        'Private drafts before publishing',
      ],
    },
    {
      label: 'SHAPE',
      title: 'Edit the Website without splitting its source of truth.',
      copy: 'Manual and AI-assisted Template edits operate on one structured, revisioned document with page hierarchy, content, design, forms, and SEO data.',
      points: [
        'Manual structured controls',
        'Focused AI-assisted edits',
        'Version history and recovery',
      ],
    },
    {
      label: 'PUBLISH',
      title: 'Go live on the right destination.',
      copy: 'Publish to a Zylora address or connect a verified custom domain after the backend evaluates the Website’s actual requirements and entitlements.',
      points: [
        'Server-evaluated plan fit',
        'Custom domain verification',
        'Deployment health and rollback path',
      ],
    },
    {
      label: 'OPERATE',
      title: 'Capture Leads and retain a clean delivery path.',
      copy: 'Valid enquiries enter the User portal with atomic Lead-credit handling. Websites can later transfer ownership or use the separate eligible export purchase flow.',
      points: [
        'Unified Lead capture',
        'Transactional ownership transfer',
        'Paid Website ZIP boundary',
      ],
    },
  ],
  steps: [
    {
      number: '01',
      title: 'Choose the creation path',
      copy: 'Template-first control or durable AI generation.',
    },
    {
      number: '02',
      title: 'Work privately',
      copy: 'Create, edit, preview, and recover drafts in the User portal.',
    },
    {
      number: '03',
      title: 'Evaluate publishing',
      copy: 'See exact Website requirements and eligible plan options.',
    },
    {
      number: '04',
      title: 'Operate or deliver',
      copy: 'Publish, capture Leads, transfer ownership, or purchase an eligible export.',
    },
  ],
  related: [
    {
      label: 'AI Website Builder',
      href: '/ai-website-builder',
      copy: 'Understand the production AI generation workflow.',
    },
    {
      label: 'Small Business Websites',
      href: '/solutions/small-business',
      copy: 'See how the product supports practical small-business Website needs.',
    },
    {
      label: 'Freelancer Workflow',
      href: '/solutions/freelancers',
      copy: 'Build and deliver client Websites while preserving singular ownership.',
    },
  ],
} satisfies SearchLandingContent;

export const metadata: Metadata = createPageMetadata({
  title: 'Website Builder Features',
  description:
    'Explore Zylora features for Website creation, AI generation, structured editing, publishing, domains, Lead capture, ownership transfer, and eligible export.',
  path: content.path,
});

const schema = serializeJsonLd({
  '@context': 'https://schema.org',
  '@type': 'WebPage',
  name: 'Zylora Website Builder Features',
  description: metadata.description,
  url: absoluteUrl(content.path),
});

export default function FeaturesPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: schema }} />
      <SearchLandingPage content={content} />
    </>
  );
}
