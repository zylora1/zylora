import { ActionLink, EmptyState, Notice, PageHeader, StatusBadge } from '@zylora/ui';
import { ArrowRight, Check } from 'lucide-react';

import { BillingPanel } from './billing-panel';
import { LeadsPanel } from './leads-panel';
import type { PortalSection } from './portal-navigation';

export function UserHomePage() {
  return (
    <div className="workspace-page workspace-page--home">
      <PageHeader
        eyebrow="Home"
        title="Publish your first website"
        description="Start with an approved professional Template, shape one structured Website document, then publish when it is ready."
        action={
          <ActionLink href="/app/templates">
            Choose a Template <ArrowRight size={17} />
          </ActionLink>
        }
      />
      <div className="first-use-layout">
        <section className="first-use-path" aria-labelledby="first-use-path-title">
          <div className="first-use-path__heading">
            <p className="workspace-kicker">Your path</p>
            <h2 id="first-use-path-title">Choose → Customize → Publish</h2>
          </div>
          <ol>
            <li>
              <span>01</span>
              <div>
                <strong>Choose an approved Template</strong>
                <p>
                  Preview the design at desktop, tablet, and mobile sizes before creating a private
                  Draft.
                </p>
              </div>
            </li>
            <li>
              <span>02</span>
              <div>
                <strong>Customize one structured document</strong>
                <p>
                  Manual and AI editing create validated revisions of the same Website—never a blank
                  canvas.
                </p>
              </div>
            </li>
            <li>
              <span>03</span>
              <div>
                <strong>Publish with verified readiness</strong>
                <p>
                  Zylora checks the Website, plan, domain, build, TLS, and health before switching
                  traffic.
                </p>
              </div>
            </li>
          </ol>
        </section>
        <aside className="first-use-boundary">
          <p className="workspace-kicker">Built-in boundaries</p>
          <h2>Clear ownership from the start.</h2>
          <ul>
            <li>
              <Check size={16} /> Multiple private Drafts
            </li>
            <li>
              <Check size={16} /> At most one live Website
            </li>
            <li>
              <Check size={16} /> Publish, Transfer, or paid ZIP
            </li>
          </ul>
          <StatusBadge tone="info">No Website selected</StatusBadge>
        </aside>
      </div>
      <Notice title="No analytics yet">
        Analytics becomes useful only after a published Website receives real activity. Zylora does
        not fill a new account with invented charts or zero-metric cards.
      </Notice>
    </div>
  );
}

export function UserSectionPage({ section }: { section: PortalSection }) {
  const action =
    section.slug === 'websites' ? (
      <ActionLink href="/app/templates">
        Choose a Template <ArrowRight size={17} />
      </ActionLink>
    ) : undefined;
  if (section.slug === 'leads') {
    return (
      <div className="workspace-page">
        <PageHeader eyebrow="Your Zylora" title={section.label} description={section.description} />
        <LeadsPanel />
      </div>
    );
  }
  if (section.slug === 'billing') {
    return (
      <div className="workspace-page">
        <PageHeader eyebrow="Your Zylora" title={section.label} description={section.description} />
        <BillingPanel />
      </div>
    );
  }
  return (
    <div className="workspace-page">
      <PageHeader eyebrow="Your Zylora" title={section.label} description={section.description} />
      <EmptyState
        eyebrow="Current state"
        title={section.emptyTitle}
        description={section.emptyDescription}
        action={action}
      />
    </div>
  );
}

export function AdminHomePage() {
  return (
    <div className="workspace-page workspace-page--admin-home">
      <PageHeader
        eyebrow="Operations"
        title="Platform overview"
        description="An isolated operational workspace for measured state, explicit decisions, and immutable evidence."
      />
      <Notice tone="warning" title="No synthetic operational summary">
        Service, commercial, Website, and security summaries will appear only when their
        authoritative APIs provide measured data.
      </Notice>
      <div className="admin-principles">
        <section>
          <span>01</span>
          <h2>Evidence before action</h2>
          <p>Every sensitive decision shows actor, target, state, reason, and recovery.</p>
        </section>
        <section>
          <span>02</span>
          <h2>One canonical transition</h2>
          <p>The console sends commands; it never invents alternate backend state changes.</p>
        </section>
        <section>
          <span>03</span>
          <h2>Audit is part of the work</h2>
          <p>Privileged operations remain attributable and reviewable.</p>
        </section>
      </div>
    </div>
  );
}

export function AdminSectionPage({ section }: { section: PortalSection }) {
  return (
    <div className="workspace-page">
      <PageHeader eyebrow="Super Admin" title={section.label} description={section.description} />
      <EmptyState
        eyebrow="Operational state"
        title={section.emptyTitle}
        description={section.emptyDescription}
        compact
      />
    </div>
  );
}
