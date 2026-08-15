import {
  ArrowRight,
  Check,
  CircleCheck,
  Cloud,
  Code2,
  FileText,
  Globe2,
  LayoutTemplate,
  MessagesSquare,
  MonitorSmartphone,
  MousePointer2,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  WandSparkles,
} from 'lucide-react';
import Link from 'next/link';

import {
  MagneticLink,
  ScrollLayer,
  SpotlightArticle,
  StickyScene,
  ViewportProgress,
} from './cinematic-motion';
import { LandingPricing } from './landing-pricing';
import { LandingPrompt } from './landing-prompt';
import { PublicFooter, PublicNavigation, PublicSite } from './public-site';
import styles from './landing-page.module.css';

const generationSteps = [
  ['01', 'Brief', 'Zylora turns the business description into audience and page requirements.'],
  ['02', 'System', 'A visual direction, content hierarchy, and responsive structure are planned.'],
  ['03', 'Build', 'The website is generated in an isolated Next.js build environment.'],
  ['04', 'Verify', 'Build, accessibility, responsive, and search foundations are checked.'],
] as const;

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

function ProductBrowser() {
  return (
    <div
      className={styles.heroProduct}
      aria-label="Animated Zylora website generation demonstration"
    >
      <div className={styles.productTopbar}>
        <div aria-hidden="true">
          <i />
          <i />
          <i />
        </div>
        <span>northline.preview.zylora.site</span>
        <small>Live preview</small>
      </div>
      <div className={styles.generationRail} aria-hidden="true">
        <span className={styles.generationLabel}>Generation plan</span>
        {['Requirements', 'Page system', 'Visual direction', 'Responsive build', 'Checks'].map(
          (step, index) => (
            <div className={styles.generationStep} key={step} style={{ '--step': index } as never}>
              <span>
                <Check aria-hidden="true" size={11} />
              </span>
              <b>{step}</b>
            </div>
          ),
        )}
      </div>
      <div className={styles.generatedSite}>
        <nav aria-label="Demonstration website navigation">
          <strong>Northline</strong>
          <div>
            <span>Work</span>
            <span>Studio</span>
            <span>Contact</span>
          </div>
        </nav>
        <div className={styles.generatedHero}>
          <small>ARCHITECTURE FOR EVERYDAY LIFE</small>
          <strong>Spaces with clarity, warmth, and purpose.</strong>
          <p>Residential architecture shaped by the way people actually live.</p>
          <span>Explore selected work</span>
        </div>
        <div className={styles.generatedProjects} aria-hidden="true">
          <i />
          <i />
          <i />
        </div>
      </div>
      <ScrollLayer
        className={styles.floatingInspector}
        input={[0, 0.34, 0.72, 1]}
        x={[80, 0, -12, -48]}
        y={[65, 0, -20, -90]}
        rotate={[5, 0, -1, -4]}
        opacity={[0, 1, 1, 0]}
      >
        <span>Type scale</span>
        <strong>Editorial / 64</strong>
        <i />
      </ScrollLayer>
      <ScrollLayer
        className={styles.mobilePreview}
        input={[0, 0.48, 0.75, 1]}
        x={[110, 110, 0, -35]}
        y={[40, 40, 0, -70]}
        rotate={[8, 8, 2, -2]}
        opacity={[0, 0, 1, 0.65]}
      >
        <span />
        <strong>Northline</strong>
        <i />
        <i />
      </ScrollLayer>
      <div className={styles.buildComplete}>
        <CircleCheck aria-hidden="true" size={16} />
        Responsive build ready
      </div>
    </div>
  );
}

function BuildWorkspace() {
  return (
    <div className={styles.workspaceVisual} aria-label="Zylora Website workspace demonstration">
      <div className={styles.workspaceTopbar}>
        <span>Northline Studio</span>
        <div>
          <MonitorSmartphone aria-hidden="true" size={14} /> Responsive preview
        </div>
        <b>Publish</b>
      </div>
      <div className={styles.workspacePages} aria-hidden="true">
        <small>PAGES</small>
        <b>Home</b>
        <span>Studio</span>
        <span>Work</span>
        <span>Journal</span>
        <span>Contact</span>
        <i />
      </div>
      <div className={styles.workspaceCanvas}>
        <ScrollLayer
          className={styles.canvasSkeleton}
          input={[0, 0.16, 0.32, 0.48]}
          opacity={[1, 1, 0.7, 0]}
          scale={[1, 1, 0.98, 0.96]}
        >
          <i />
          <i />
          <i />
          <i />
        </ScrollLayer>
        <ScrollLayer
          className={styles.canvasWebsite}
          input={[0.18, 0.4, 0.72, 1]}
          y={[70, 0, -12, -32]}
          scale={[0.96, 1, 0.97, 0.9]}
          rotateX={[4, 0, 1, 5]}
          opacity={[0, 1, 1, 0.86]}
        >
          <nav>
            <b>Northline</b>
            <span>Work&nbsp;&nbsp; Studio&nbsp;&nbsp; Contact</span>
          </nav>
          <div>
            <small>THOUGHTFUL RESIDENTIAL ARCHITECTURE</small>
            <strong>Make space for what matters.</strong>
            <span>View our work</span>
          </div>
          <section aria-hidden="true">
            <i />
            <i />
          </section>
        </ScrollLayer>
      </div>
      <ScrollLayer
        className={styles.workspacePrompt}
        input={[0, 0.2, 0.54, 0.8]}
        x={[80, 0, 0, -40]}
        y={[100, 0, -10, -80]}
        opacity={[0, 1, 1, 0]}
      >
        <Sparkles aria-hidden="true" size={14} />
        <span>Make the opening feel warmer and add a clear enquiry path.</span>
        <Send aria-hidden="true" size={13} />
      </ScrollLayer>
      <ScrollLayer
        className={styles.workspaceMobile}
        input={[0.48, 0.7, 0.86, 1]}
        x={[120, 0, -20, -42]}
        y={[70, 0, -20, -50]}
        rotate={[7, 1, -1, -3]}
        opacity={[0, 1, 1, 0.8]}
      >
        <b>Northline</b>
        <i />
        <span />
      </ScrollLayer>
    </div>
  );
}

export function LandingPage() {
  return (
    <PublicSite>
      <ViewportProgress />
      <PublicNavigation />
      <main className={styles.main}>
        <StickyScene
          className={styles.hero}
          stageClassName={styles.heroStage}
          labelledBy="landing-title"
        >
          <div className={styles.heroGrid} aria-hidden="true" />
          <ScrollLayer
            className={styles.heroCopy}
            input={[0, 0.46, 0.78, 1]}
            y={[0, -24, -70, -120]}
            scale={[1, 0.98, 0.94, 0.9]}
            opacity={[1, 1, 0.82, 0.12]}
          >
            <p className={styles.eyebrow}>AI website builder + professional Templates</p>
            <h1 id="landing-title">
              Build a professional website <span>your way.</span>
            </h1>
            <p className={styles.heroLede}>
              Start with a validated Template when you want control. Describe the business and build
              with Zylora AI when you want momentum.
            </p>
          </ScrollLayer>
          <ScrollLayer
            className={styles.heroPrompt}
            input={[0, 0.34, 0.68, 1]}
            y={[0, -15, -70, -140]}
            opacity={[1, 1, 0.72, 0]}
          >
            <LandingPrompt />
          </ScrollLayer>
          <ScrollLayer
            className={styles.heroProductLayer}
            input={[0, 0.2, 0.65, 1]}
            y={[160, 24, -35, -150]}
            scale={[0.82, 1, 1.02, 0.9]}
            rotateX={[9, 0, 0, -4]}
            opacity={[0.4, 1, 1, 0.66]}
          >
            <ProductBrowser />
          </ScrollLayer>
          <a className={styles.scrollCue} href="#product">
            <MousePointer2 aria-hidden="true" size={14} /> Scroll to build
          </a>
        </StickyScene>

        <section className={styles.proofBand} aria-label="Product facts">
          <p>A production path, not a blank canvas.</p>
          <div>
            <span>
              <strong>1,000+</strong> prepared starting points
            </span>
            <span>
              <strong>2</strong> ways to begin
            </span>
            <span>
              <strong>1</strong> structured source of truth
            </span>
            <span>
              <strong>0</strong> paid decisions trusted to the browser
            </span>
          </div>
        </section>

        <StickyScene
          className={styles.productStory}
          stageClassName={styles.productStage}
          id="product"
          labelledBy="product-title"
        >
          <div className={styles.storyCopy}>
            <p className={styles.eyebrow}>A website takes shape as you move</p>
            <h2 id="product-title">From brief to verified build. One continuous system.</h2>
            <ol>
              {generationSteps.map(([number, title, copy]) => (
                <li key={number}>
                  <span>{number}</span>
                  <div>
                    <h3>{title}</h3>
                    <p>{copy}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
          <BuildWorkspace />
        </StickyScene>

        <section className={styles.paths} aria-labelledby="paths-title">
          <div className={styles.sectionHeading}>
            <p className={styles.eyebrow}>Two deliberate starting points</p>
            <h2 id="paths-title">Choose the kind of control you need today.</h2>
            <p>
              Both paths lead to a responsive production website. They differ in how the first
              version is created, not in the quality bar applied before publishing.
            </p>
          </div>
          <div className={styles.pathGrid}>
            <SpotlightArticle className={styles.templatePath}>
              <span className={styles.pathNumber}>01 / TEMPLATE</span>
              <LayoutTemplate aria-hidden="true" size={28} />
              <h3>Begin with an approved foundation.</h3>
              <p>
                Browse before answering questions, create a private multi-page draft, then edit the
                same structured Website document manually or with AI.
              </p>
              <ul>
                <li>
                  <Check aria-hidden="true" size={14} /> Responsive, validated starting point
                </li>
                <li>
                  <Check aria-hidden="true" size={14} /> Real page hierarchy and SEO defaults
                </li>
                <li>
                  <Check aria-hidden="true" size={14} /> Revision-safe editing
                </li>
              </ul>
              <MagneticLink className={styles.textLink} href="/templates">
                Explore Templates <ArrowRight aria-hidden="true" size={15} />
              </MagneticLink>
              <div className={styles.templateStack} aria-hidden="true">
                <i />
                <i />
                <i />
              </div>
            </SpotlightArticle>
            <SpotlightArticle className={styles.aiPath}>
              <span className={styles.pathNumber}>02 / ZYLORA AI</span>
              <WandSparkles aria-hidden="true" size={28} />
              <h3>Describe the business. Generate the system.</h3>
              <p>
                Zylora plans the page architecture, visual direction, responsive behavior, and
                search foundations before producing an isolated Next.js build.
              </p>
              <ul>
                <li>
                  <Check aria-hidden="true" size={14} /> Business brief becomes page requirements
                </li>
                <li>
                  <Check aria-hidden="true" size={14} /> Build and quality checks run before handoff
                </li>
                <li>
                  <Check aria-hidden="true" size={14} /> Durable progress survives refresh
                </li>
              </ul>
              <MagneticLink className={styles.textLink} href="/signup?intent=ai">
                Build with AI <ArrowRight aria-hidden="true" size={15} />
              </MagneticLink>
              <div className={styles.codeSystem} aria-hidden="true">
                <span>app/</span>
                <b>layout.tsx</b>
                <b>page.tsx</b>
                <span>public/</span>
                <b>brand.svg</b>
              </div>
            </SpotlightArticle>
          </div>
        </section>

        <section className={styles.templateShowcase} aria-labelledby="templates-title">
          <div className={styles.sectionHeading}>
            <p className={styles.eyebrow}>Template catalogue</p>
            <h2 id="templates-title">Starting points with a point of view.</h2>
            <p>
              Each published Template is reviewed as a complete Website system—not a decorative
              thumbnail or an untested collection of sections.
            </p>
          </div>
          <div className={styles.templateRail}>
            {[
              ['Clinic', 'Trust-first care', 'calm', 'Care, clearly explained.'],
              ['Restaurant', 'Warm local character', 'warm', 'A table worth gathering around.'],
              ['Consultant', 'Clear expertise', 'editorial', 'Complex work. Clear decisions.'],
            ].map(([category, title, tone, headline]) => (
              <article key={category} className={styles.templateCard} data-tone={tone}>
                <div className={styles.templateBrowser}>
                  <span />
                  <nav>
                    <b>{title}</b>
                    <i />
                  </nav>
                  <strong>{headline}</strong>
                  <div aria-hidden="true">
                    <i />
                    <i />
                  </div>
                </div>
                <p>{category} Website Template</p>
                <span>{title}</span>
              </article>
            ))}
          </div>
          <MagneticLink className={styles.primaryLink} href="/templates">
            Browse validated Templates <ArrowRight aria-hidden="true" size={16} />
          </MagneticLink>
        </section>

        <StickyScene
          className={styles.publishStory}
          stageClassName={styles.publishStage}
          id="ai"
          labelledBy="publish-title"
        >
          <div className={styles.publishCopy}>
            <p className={styles.eyebrow}>Build → publish → learn</p>
            <h2 id="publish-title">The website does not stop at launch.</h2>
            <p>
              Publish to a Zylora address or verified custom domain. Valid enquiries become Leads in
              the User portal, with server-authoritative credit and ownership rules behind them.
            </p>
            <MagneticLink className={styles.primaryLink} href="/signup">
              Start a Website <ArrowRight aria-hidden="true" size={16} />
            </MagneticLink>
          </div>
          <div className={styles.publishOrbit} aria-label="Publishing and Lead workflow">
            <ScrollLayer
              className={styles.orbitWebsite}
              input={[0, 0.24, 0.72, 1]}
              x={[-80, 0, 0, -45]}
              y={[60, 0, -20, -70]}
              rotate={[-5, 0, 1, -3]}
              scale={[0.9, 1, 0.95, 0.86]}
              opacity={[0, 1, 1, 0.74]}
            >
              <span>northline.studio</span>
              <strong>Make space for what matters.</strong>
              <i />
            </ScrollLayer>
            <ScrollLayer
              className={styles.orbitDomain}
              input={[0.18, 0.38, 0.72, 1]}
              x={[90, 0, -20, -70]}
              y={[-45, 0, -20, -55]}
              opacity={[0, 1, 1, 0.7]}
            >
              <Globe2 aria-hidden="true" size={17} />
              <span>Custom domain</span>
              <b>Verified</b>
            </ScrollLayer>
            <ScrollLayer
              className={styles.orbitLead}
              input={[0.42, 0.66, 0.86, 1]}
              x={[120, 0, -10, -38]}
              y={[90, 0, -20, -52]}
              rotate={[6, 0, -1, -2]}
              opacity={[0, 1, 1, 0.76]}
            >
              <MessagesSquare aria-hidden="true" size={17} />
              <small>NEW WEBSITE LEAD</small>
              <strong>Residential renovation enquiry</strong>
              <span>Captured safely · credit recorded once</span>
            </ScrollLayer>
          </div>
        </StickyScene>

        <section
          className={styles.freelancers}
          id="freelancers"
          aria-labelledby="freelancers-title"
        >
          <div>
            <p className={styles.eyebrow}>For freelancers and studios</p>
            <h2 id="freelancers-title">Client work without a second account system.</h2>
            <p>
              A User can own multiple drafts, shape the work privately, then transfer the Website to
              another Zylora User or purchase an eligible deployable export. Ownership remains
              singular and auditable throughout.
            </p>
            <MagneticLink className={styles.textLink} href="/solutions/freelancers">
              See the freelancer workflow <ArrowRight aria-hidden="true" size={15} />
            </MagneticLink>
          </div>
          <ol className={styles.workflow}>
            <li>
              <span>01</span>
              <div>
                <b>Create</b>
                <small>Template or Zylora AI</small>
              </div>
            </li>
            <li>
              <span>02</span>
              <div>
                <b>Shape</b>
                <small>Private, revision-safe work</small>
              </div>
            </li>
            <li>
              <span>03</span>
              <div>
                <b>Deliver</b>
                <small>Transfer ownership or eligible export</small>
              </div>
            </li>
          </ol>
        </section>

        <section className={styles.foundations} aria-labelledby="foundations-title">
          <div className={styles.sectionHeading}>
            <p className={styles.eyebrow}>The invisible quality layer</p>
            <h2 id="foundations-title">
              Built to be understood by people, browsers, and crawlers.
            </h2>
          </div>
          <div className={styles.foundationLedger}>
            <article>
              <Code2 aria-hidden="true" />
              <span>01</span>
              <div>
                <h3>Performance-minded output</h3>
                <p>Responsive rendering, reserved media space, and a deliberate loading path.</p>
              </div>
            </article>
            <article>
              <Search aria-hidden="true" />
              <span>02</span>
              <div>
                <h3>Search foundations</h3>
                <p>
                  Semantic HTML, metadata, canonicals, sitemap rules, and crawl-safe boundaries.
                </p>
              </div>
            </article>
            <article>
              <ShieldCheck aria-hidden="true" />
              <span>03</span>
              <div>
                <h3>Authoritative product rules</h3>
                <p>Publishing, plans, ownership, and paid capability stay on the server.</p>
              </div>
            </article>
            <article>
              <FileText aria-hidden="true" />
              <span>04</span>
              <div>
                <h3>Recoverable work</h3>
                <p>
                  Validated revisions for Template editing and immutable artifacts for AI builds.
                </p>
              </div>
            </article>
          </div>
        </section>

        <section className={styles.pricingSection} aria-label="Website builder pricing overview">
          <LandingPricing />
        </section>

        <section className={styles.faq} aria-labelledby="faq-title">
          <div>
            <p className={styles.eyebrow}>Questions before you begin</p>
            <h2 id="faq-title">The practical details, clearly stated.</h2>
          </div>
          <div className={styles.faqList}>
            {faqs.map(([question, answer], index) => (
              <details key={question} open={index === 0}>
                <summary>{question}</summary>
                <p>{answer}</p>
              </details>
            ))}
          </div>
        </section>

        <section className={styles.finalCta} aria-labelledby="final-cta-title">
          <div className={styles.ctaOrbit} aria-hidden="true">
            <Cloud />
            <Sparkles />
          </div>
          <p className={styles.eyebrow}>A clear first step</p>
          <h2 id="final-cta-title">Build the website your business can grow into.</h2>
          <p>Choose a professional Template or describe the outcome you want Zylora AI to build.</p>
          <div>
            <MagneticLink className={styles.primaryLink} href="/signup">
              Start building <ArrowRight aria-hidden="true" size={16} />
            </MagneticLink>
            <Link className={styles.secondaryLink} href="/templates">
              Explore Templates
            </Link>
          </div>
        </section>
      </main>
      <PublicFooter />
    </PublicSite>
  );
}
