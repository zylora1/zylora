import type { Metadata } from 'next';

import { SearchLandingPage, type SearchLandingContent } from '@/components/search-landing';
import { absoluteUrl, createPageMetadata, serializeJsonLd } from '@/lib/seo';

const path = '/solutions/small-business';
const content = {
  eyebrow: 'Website builder for small businesses',
  title: 'A credible business website without assembling a fragile stack.',
  intro:
    'Build the pages customers need to understand the business, see the offer, find practical details, and make an enquiry—then publish on a Zylora address or a verified custom domain.',
  proof:
    'Zylora is designed for real operating details: multi-page structure, responsive presentation, clear enquiry paths, domain connection, Lead capture, and recoverable Website work.',
  path,
  primaryCta: { label: 'Build a small business Website', href: '/signup' },
  secondaryCta: { label: 'Browse business Templates', href: '/templates' },
  breadcrumbs: [{ label: 'Small business', href: path }],
  sections: [
    {
      label: 'CLARITY',
      title: 'Explain the business before asking for the enquiry.',
      copy: 'Use a clear page hierarchy for services, proof, location or service area, practical questions, and the next action a visitor should take.',
      points: [
        'Focused service pages',
        'Practical contact and location details',
        'One clear primary conversion path',
      ],
    },
    {
      label: 'TRUST',
      title: 'Start from a professional visual and content system.',
      copy: 'Validated Templates provide a considered foundation. Zylora AI can instead plan and generate a Website around the specific business description.',
      points: [
        'Responsive visual hierarchy',
        'No mandatory blank canvas',
        'Content remains editable and semantic',
      ],
    },
    {
      label: 'DISCOVERY',
      title: 'Give search engines a clean technical foundation.',
      copy: 'Metadata, canonical paths, semantic headings, sitemap behavior, and crawl boundaries are treated as part of the Website system rather than a final plugin.',
      points: [
        'Semantic page structure',
        'Page-level metadata and canonicals',
        'Performance-minded responsive output',
      ],
    },
    {
      label: 'ENQUIRIES',
      title: 'Keep new business attached to the Website that created it.',
      copy: 'Valid enquiry-form submissions become Leads in the User portal, with Website context and atomic credit handling preserved by the backend.',
      points: [
        'Unified Lead records',
        'Website-specific context',
        'One valid Lead consumes one credit',
      ],
    },
  ],
  steps: [
    {
      number: '01',
      title: 'Choose a relevant starting point',
      copy: 'Browse by business fit or describe the Website to Zylora AI.',
    },
    {
      number: '02',
      title: 'Add the practical business detail',
      copy: 'Services, locations, opening information, FAQs, proof, and enquiry paths.',
    },
    {
      number: '03',
      title: 'Inspect every viewport',
      copy: 'Review the responsive Website before it becomes public.',
    },
    {
      number: '04',
      title: 'Publish and respond',
      copy: 'Connect the destination, go live, and handle captured Leads in the portal.',
    },
  ],
  related: [
    {
      label: 'Website Builder',
      href: '/website-builder',
      copy: 'Learn how the Template-first structured workflow operates.',
    },
    {
      label: 'AI Website Builder',
      href: '/ai-website-builder',
      copy: 'Generate a Website from a clear business description.',
    },
    {
      label: 'Pricing',
      href: '/pricing',
      copy: 'Compare the current server-provided publishing plans.',
    },
  ],
} satisfies SearchLandingContent;

export const metadata: Metadata = createPageMetadata({
  title: 'Website Builder for Small Businesses',
  description:
    'Create a professional small-business website with clear services, responsive design, search foundations, custom domains, and built-in Lead capture.',
  path,
});

const schema = serializeJsonLd({
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'WebPage',
      name: 'Website Builder for Small Businesses',
      description: metadata.description,
      url: absoluteUrl(path),
    },
    {
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'Home', item: absoluteUrl('/') },
        { '@type': 'ListItem', position: 2, name: 'Small business', item: absoluteUrl(path) },
      ],
    },
  ],
});

export default function SmallBusinessPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: schema }} />
      <SearchLandingPage content={content} />
    </>
  );
}
