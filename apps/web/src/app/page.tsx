import Link from 'next/link';

import { PublicFooter, PublicNavigation, PublicSite } from '@/components/public-site';
import styles from './public-home.module.css';

const faqs = [
  [
    'Can I start without choosing a paid plan?',
    'Yes. Create, edit, preview, transfer, and prepare an any-size draft before publishing. Zylora evaluates the publishing plan only when you choose to go live.',
  ],
  [
    'Can I use AI and edit manually?',
    'Yes. AI and manual editing work on the same structured Website, so every change remains part of one revision-safe draft.',
  ],
  [
    'Can I move a Website to a client?',
    'Yes. A Website has one current owner. You can transfer it through the portal or purchase a deployable Website export where eligible.',
  ],
] as const;

const origin = process.env.NEXT_PUBLIC_WEB_ORIGIN ?? 'http://localhost:3000';
const structuredData = JSON.stringify([
  {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'Zylora',
    url: origin,
  },
  {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'Zylora',
    url: origin,
  },
  {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faqs.map(([question, answer]) => ({
      '@type': 'Question',
      name: question,
      acceptedAnswer: { '@type': 'Answer', text: answer },
    })),
  },
]).replace(/</g, '\\u003c');

export default function HomePage() {
  return (
    <PublicSite>
      <PublicNavigation />
      <main>
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: structuredData }} />
        <section className={styles.hero}>
          <div>
            <p className="eyebrow">A better starting point for a serious Website</p>
            <h1>Choose the shape. Make it unmistakably yours.</h1>
            <p className={styles.lede}>
              Start with a professional Template, refine every page manually or with AI, and publish
              when your Website is ready to represent you.
            </p>
            <div className={styles.heroActions}>
              <Link href="/templates" className={styles.primary}>
                Explore Templates
              </Link>
              <Link href="/pricing" className={styles.secondary}>
                See publishing plans
              </Link>
            </div>
          </div>
          <div className={styles.art} aria-label="Website workflow illustration">
            <p>Template</p>
            <span>+</span>
            <p>Your point of view</p>
            <span>=</span>
            <strong>A Website you own</strong>
          </div>
        </section>
        <section className={styles.proof} aria-label="How Zylora works">
          <article>
            <span>01</span>
            <h2>Choose a proven foundation</h2>
            <p>
              Explore approved, responsive Templates built for real businesses and clear conversion
              paths.
            </p>
          </article>
          <article>
            <span>02</span>
            <h2>Shape every page with intent</h2>
            <p>
              Edit content, sections, visual settings, navigation, and page hierarchy yourself - or
              ask AI for focused help.
            </p>
          </article>
          <article>
            <span>03</span>
            <h2>Publish, transfer, or export</h2>
            <p>
              Manage drafts, live publishing, ownership transfer, Leads, chatbot, analytics, and
              billing from one portal.
            </p>
          </article>
        </section>
        <section className={styles.feature}>
          <div>
            <p className="eyebrow">One structured Website, not a blank canvas</p>
            <h2>Manual precision and AI momentum, working together.</h2>
            <p>
              Every Zylora Website begins with a validated Template. Your pages, navigation, SEO
              settings, revisions, and publishing decisions remain coherent as the work grows.
            </p>
            <Link href="/templates">Find your starting point &rarr;</Link>
          </div>
          <ul>
            <li>Multi-page drafts without premature plan limits</li>
            <li>Responsive previews before publishing</li>
            <li>Revision-safe AI changes and restore</li>
            <li>Lead capture, chatbot, and measured analytics</li>
          </ul>
        </section>
        <section className={styles.faq}>
          <div>
            <p className="eyebrow">Clear before you begin</p>
            <h2>Questions worth answering.</h2>
          </div>
          <div>
            {faqs.map(([question, answer]) => (
              <details key={question}>
                <summary>{question}</summary>
                <p>{answer}</p>
              </details>
            ))}
          </div>
        </section>
        <section className={styles.final}>
          <p className="eyebrow">Ready when you are</p>
          <h2>Build a Website with a clear path to launch.</h2>
          <Link href="/signup" className={styles.primary}>
            Create your account
          </Link>
        </section>
      </main>
      <PublicFooter />
    </PublicSite>
  );
}
