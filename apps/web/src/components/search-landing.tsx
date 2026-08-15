import { ArrowRight, Check, ChevronRight } from 'lucide-react';
import Link from 'next/link';

import { MagneticLink, SpotlightArticle } from './cinematic-motion';
import { PublicFooter, PublicNavigation, PublicSite } from './public-site';
import styles from './search-landing.module.css';

export type SearchLandingContent = {
  eyebrow: string;
  title: string;
  intro: string;
  proof: string;
  path: string;
  primaryCta: { label: string; href: string };
  secondaryCta: { label: string; href: string };
  breadcrumbs?: ReadonlyArray<{ label: string; href: string }> | undefined;
  sections: ReadonlyArray<{
    label: string;
    title: string;
    copy: string;
    points: readonly string[];
  }>;
  steps: ReadonlyArray<{ number: string; title: string; copy: string }>;
  related: ReadonlyArray<{ label: string; href: string; copy: string }>;
};

export function SearchLandingPage({ content }: { content: SearchLandingContent }) {
  return (
    <PublicSite>
      <PublicNavigation />
      <main className={styles.main}>
        <header className={styles.hero}>
          {content.breadcrumbs ? (
            <nav className={styles.breadcrumbs} aria-label="Breadcrumb">
              <Link href="/">Home</Link>
              {content.breadcrumbs.map((item) => (
                <span key={item.href}>
                  <ChevronRight aria-hidden="true" size={12} />
                  <Link href={item.href}>{item.label}</Link>
                </span>
              ))}
            </nav>
          ) : null}
          <p className={styles.eyebrow}>{content.eyebrow}</p>
          <h1>{content.title}</h1>
          <p className={styles.intro}>{content.intro}</p>
          <div className={styles.actions}>
            <MagneticLink className={styles.primaryAction} href={content.primaryCta.href}>
              {content.primaryCta.label} <ArrowRight aria-hidden="true" size={16} />
            </MagneticLink>
            <Link className={styles.secondaryAction} href={content.secondaryCta.href}>
              {content.secondaryCta.label}
            </Link>
          </div>
          <div className={styles.systemVisual} aria-hidden="true">
            <span>Brief</span>
            <i />
            <span>Structure</span>
            <i />
            <span>Website</span>
            <i />
            <span>Publish</span>
          </div>
        </header>

        <aside className={styles.proof}>{content.proof}</aside>

        <section className={styles.capabilities} aria-label={`${content.eyebrow} capabilities`}>
          {content.sections.map((section, index) => (
            <SpotlightArticle className={styles.capability} key={section.title}>
              <span>
                {String(index + 1).padStart(2, '0')} / {section.label}
              </span>
              <h2>{section.title}</h2>
              <p>{section.copy}</p>
              <ul>
                {section.points.map((point) => (
                  <li key={point}>
                    <Check aria-hidden="true" size={14} /> {point}
                  </li>
                ))}
              </ul>
            </SpotlightArticle>
          ))}
        </section>

        <section className={styles.process} aria-labelledby="search-page-process">
          <div>
            <p className={styles.eyebrow}>A clear route to launch</p>
            <h2 id="search-page-process">How the work moves forward.</h2>
          </div>
          <ol>
            {content.steps.map((step) => (
              <li key={step.number}>
                <span>{step.number}</span>
                <div>
                  <h3>{step.title}</h3>
                  <p>{step.copy}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section className={styles.related} aria-labelledby="related-title">
          <div>
            <p className={styles.eyebrow}>Continue exploring</p>
            <h2 id="related-title">Choose the next useful detail.</h2>
          </div>
          <div>
            {content.related.map((item) => (
              <Link href={item.href} key={item.href}>
                <span>{item.label}</span>
                <p>{item.copy}</p>
                <ArrowRight aria-hidden="true" size={16} />
              </Link>
            ))}
          </div>
        </section>

        <section className={styles.finalCta}>
          <p className={styles.eyebrow}>Start with the real product</p>
          <h2>{content.primaryCta.label}.</h2>
          <MagneticLink className={styles.primaryAction} href={content.primaryCta.href}>
            {content.primaryCta.label} <ArrowRight aria-hidden="true" size={16} />
          </MagneticLink>
        </section>
      </main>
      <PublicFooter />
    </PublicSite>
  );
}
