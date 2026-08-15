import type { Metadata } from 'next';

import { SearchLandingPage, type SearchLandingContent } from '@/components/search-landing';
import { absoluteUrl, createPageMetadata, serializeJsonLd } from '@/lib/seo';

const content = {
  eyebrow: 'Zylora AI website builder',
  title: 'Describe the business. Generate the production website.',
  intro:
    'Zylora AI turns a clear business description into requirements, page architecture, content direction, a responsive visual system, and a verified Next.js build—without pretending a one-line prompt removes the need for quality checks.',
  proof:
    'AI generation is a durable, isolated workflow. Progress survives refresh, build failures are reported honestly, and a successful result is packaged as an immutable deployment artifact.',
  path: '/ai-website-builder',
  primaryCta: { label: 'Create a Website with AI', href: '/signup?intent=ai' },
  secondaryCta: { label: 'Start from a Template', href: '/templates' },
  sections: [
    {
      label: 'UNDERSTAND',
      title: 'The prompt becomes a real Website brief.',
      copy: 'Zylora identifies the business, audience, goals, required pages, and practical conversion path before generation begins.',
      points: [
        'Business and audience requirements',
        'Page and content goals',
        'Clear scope before build work',
      ],
    },
    {
      label: 'PLAN',
      title: 'Architecture and visual direction come before code.',
      copy: 'The system plans page structure, content hierarchy, responsive behavior, and a coherent design direction for the specific brief.',
      points: ['Page architecture', 'Content hierarchy', 'Responsive visual system'],
    },
    {
      label: 'GENERATE',
      title: 'A real Next.js project is built in isolation.',
      copy: 'Generation runs behind an explicit job boundary rather than inside the browser. The resulting project is treated as production code, not a decorative preview.',
      points: [
        'Isolated build environment',
        'Durable project state',
        'No browser-granted capability',
      ],
    },
    {
      label: 'VERIFY',
      title: 'The result must build and withstand inspection.',
      copy: 'Responsive behavior, semantic structure, accessibility, search foundations, and the production build are checked before the artifact is ready.',
      points: [
        'Production build verification',
        'Responsive and accessibility review',
        'Metadata and sitemap foundations',
      ],
    },
  ],
  steps: [
    {
      number: '01',
      title: 'Describe the outcome',
      copy: 'Explain the business, audience, offer, and the action the Website should support.',
    },
    {
      number: '02',
      title: 'Review the plan',
      copy: 'The project records the Website direction and durable generation state.',
    },
    {
      number: '03',
      title: 'Generate and repair',
      copy: 'Zylora builds, inspects, and repairs within the bounded generation workflow.',
    },
    {
      number: '04',
      title: 'Preview the artifact',
      copy: 'Inspect the generated Website before making any publishing decision.',
    },
  ],
  related: [
    {
      label: 'Template-first Website Builder',
      href: '/website-builder',
      copy: 'Choose the structured path when you want a prepared foundation and direct editing control.',
    },
    {
      label: 'Features',
      href: '/features',
      copy: 'See what happens after creation: editing, domains, publishing, Leads, transfer, and export.',
    },
    {
      label: 'Pricing',
      href: '/pricing',
      copy: 'Compare the backend-provided monthly publishing plans.',
    },
  ],
} satisfies SearchLandingContent;

export const metadata: Metadata = createPageMetadata({
  title: 'AI Website Builder for Business Websites',
  description:
    'Describe your business and let Zylora AI plan, generate, build, and verify a responsive production Next.js website with strong search foundations.',
  path: content.path,
});

const schema = serializeJsonLd({
  '@context': 'https://schema.org',
  '@type': 'SoftwareApplication',
  name: 'Zylora AI Website Builder',
  applicationCategory: 'BusinessApplication',
  operatingSystem: 'Web',
  description: metadata.description,
  url: absoluteUrl(content.path),
});

export default function AiWebsiteBuilderPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: schema }} />
      <SearchLandingPage content={content} />
    </>
  );
}
