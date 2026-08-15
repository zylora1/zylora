import type { Metadata } from 'next';

import { SearchLandingPage, type SearchLandingContent } from '@/components/search-landing';
import { absoluteUrl, createPageMetadata, serializeJsonLd } from '@/lib/seo';

const content = {
  eyebrow: 'Structured website builder',
  title: 'A website builder that starts with a complete foundation.',
  intro:
    'Choose a validated, approved Website Template, create a private multi-page draft, and shape the content, design, navigation, forms, and search settings without beginning from an empty canvas.',
  proof:
    'Zylora uses one structured, versioned Website document for manual and AI-assisted editing. Publishing eligibility and paid capabilities are evaluated by the backend when you decide to go live.',
  path: '/website-builder',
  primaryCta: { label: 'Browse Website Templates', href: '/templates' },
  secondaryCta: { label: 'Compare publishing plans', href: '/pricing' },
  sections: [
    {
      label: 'START',
      title: 'Begin with a Website, not a pile of blocks.',
      copy: 'Every public Template has already passed structural, responsive, accessibility, and quality validation before it can become your draft.',
      points: [
        'Multi-page hierarchy',
        'Responsive starting states',
        'Prepared navigation and content structure',
      ],
    },
    {
      label: 'EDIT',
      title: 'Manual control and AI assistance share one source.',
      copy: 'Change content and design through structured controls, or request a focused AI edit. Both update the same revision-safe Website document.',
      points: [
        'Recoverable revisions',
        'Structured content changes',
        'No competing AI-only document',
      ],
    },
    {
      label: 'PREVIEW',
      title: 'Inspect the actual responsive result.',
      copy: 'Preview the Website at desktop, tablet, and mobile widths while keeping the document hierarchy and navigation behavior intact.',
      points: [
        'Desktop, tablet, and mobile preview',
        'Meaningful DOM order',
        'Draft remains private',
      ],
    },
    {
      label: 'PUBLISH',
      title: 'Choose a plan only when the Website needs one.',
      copy: 'Drafting and previewing come first. At publish time Zylora evaluates the pages, features, domain choice, and entitlements the live Website requires.',
      points: [
        'Server-authoritative eligibility',
        'Zylora address or verified custom domain',
        'One live Website per User',
      ],
    },
  ],
  steps: [
    {
      number: '01',
      title: 'Browse',
      copy: 'Explore approved Templates by fit and inspect responsive previews.',
    },
    {
      number: '02',
      title: 'Create a draft',
      copy: 'Instantiate an independent private Website document owned by your User account.',
    },
    {
      number: '03',
      title: 'Shape the Website',
      copy: 'Edit pages, content, design, navigation, forms, and SEO settings.',
    },
    {
      number: '04',
      title: 'Publish deliberately',
      copy: 'Review requirements, choose an eligible plan, and select the publishing destination.',
    },
  ],
  related: [
    {
      label: 'AI Website Builder',
      href: '/ai-website-builder',
      copy: 'See the separate path for generating a production Website from a business description.',
    },
    {
      label: 'Website Templates',
      href: '/templates',
      copy: 'Browse the catalogue of validated, approved starting points.',
    },
    {
      label: 'Features',
      href: '/features',
      copy: 'Review editing, publishing, Lead capture, transfer, and export capabilities.',
    },
  ],
} satisfies SearchLandingContent;

export const metadata: Metadata = createPageMetadata({
  title: 'Website Builder for Small Businesses',
  description:
    'Build a professional multi-page business website from a validated Template. Edit manually or with AI, preview responsively, and publish when ready.',
  path: content.path,
});

const schema = serializeJsonLd({
  '@context': 'https://schema.org',
  '@type': 'WebPage',
  name: 'Website Builder for Small Businesses',
  description: metadata.description,
  url: absoluteUrl(content.path),
});

export default function WebsiteBuilderPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: schema }} />
      <SearchLandingPage content={content} />
    </>
  );
}
