import type { Metadata } from 'next';

import { LandingPage } from '@/components/landing-page';
import { absoluteUrl, createPageMetadata, serializeJsonLd, siteIdentity } from '@/lib/seo';

const faqs = [
  [
    'Can I build before choosing a plan?',
    'Yes. You can create, edit, and preview a private draft before publishing. Zylora evaluates the required plan only when you decide to go live.',
  ],
  [
    'Do I have to start from a blank page?',
    'No. Choose a validated, approved Template for a structured starting point, or use Zylora AI to generate a production website from a clear business description.',
  ],
  [
    'Can I edit manually and with AI?',
    'Template projects use one revision-safe Website document for manual and AI-assisted edits, so both paths update the same structured source.',
  ],
  [
    'Can I hand a website to a client?',
    'A Website has one current owner. Eligible projects can be transferred to another Zylora User, or purchased as a deployable Website export through the separate export flow.',
  ],
] as const;

export const metadata: Metadata = createPageMetadata({
  title: 'Zylora — AI Website Builder for Small Businesses',
  absoluteTitle: true,
  description:
    'Build a professional business website with Zylora AI or start from a validated Template. Edit, preview, publish, connect a domain, and capture Leads in one platform.',
  path: '/',
});

const structuredData = serializeJsonLd({
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Organization',
      '@id': `${absoluteUrl('/')}#organization`,
      name: siteIdentity.name,
      url: absoluteUrl('/'),
      logo: absoluteUrl('/icon.svg'),
      description: siteIdentity.description,
    },
    {
      '@type': 'WebSite',
      '@id': `${absoluteUrl('/')}#website`,
      name: siteIdentity.name,
      url: absoluteUrl('/'),
      publisher: { '@id': `${absoluteUrl('/')}#organization` },
    },
    {
      '@type': 'SoftwareApplication',
      '@id': `${absoluteUrl('/')}#software`,
      name: siteIdentity.name,
      url: absoluteUrl('/'),
      applicationCategory: 'BusinessApplication',
      operatingSystem: 'Web',
      description: siteIdentity.description,
      featureList: [
        'AI website generation',
        'Validated website Templates',
        'Manual and AI-assisted editing',
        'Website publishing and custom domains',
        'Lead capture',
      ],
      publisher: { '@id': `${absoluteUrl('/')}#organization` },
    },
    {
      '@type': 'FAQPage',
      mainEntity: faqs.map(([question, answer]) => ({
        '@type': 'Question',
        name: question,
        acceptedAnswer: { '@type': 'Answer', text: answer },
      })),
    },
  ],
});

export default function HomePage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: structuredData }} />
      <LandingPage />
    </>
  );
}
