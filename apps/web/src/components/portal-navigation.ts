export type PortalSection = {
  slug: string;
  label: string;
  description: string;
  emptyTitle: string;
  emptyDescription: string;
};

export const userSections: PortalSection[] = [
  {
    slug: 'websites',
    label: 'Websites',
    description: 'Drafts, live Website state, and the next safe action.',
    emptyTitle: 'No Websites yet',
    emptyDescription:
      'Every Website begins with an approved Template. Choose one when you are ready to start.',
  },
  {
    slug: 'templates',
    label: 'Templates',
    description: 'Browse approved starting points for your Website.',
    emptyTitle: 'The approved catalogue is being prepared',
    emptyDescription:
      'Only validated and published Templates will appear here. Blank-canvas creation is not available.',
  },
  {
    slug: 'leads',
    label: 'Leads',
    description: 'Website enquiry-form submissions in one place.',
    emptyTitle: 'No Leads to review',
    emptyDescription:
      'Leads will appear after a published Website receives a valid enquiry form submission.',
  },
  {
    slug: 'analytics',
    label: 'Analytics',
    description: 'Verified activity from your published Website.',
    emptyTitle: 'Analytics begins with real traffic',
    emptyDescription:
      'There are no charts or zero-value metrics to show before a Website is published and receives activity.',
  },
  {
    slug: 'credits',
    label: 'Credits',
    description: 'Lead-credit balance and an auditable transaction ledger.',
    emptyTitle: 'No credit activity yet',
    emptyDescription:
      'Your balance and ledger will appear when a plan or verified Lead transaction creates activity.',
  },
  {
    slug: 'billing',
    label: 'Billing',
    description: 'Subscriptions, invoices, and verified payment state.',
    emptyTitle: 'No billing records',
    emptyDescription:
      'Plans and payment records will appear only after the server confirms a real commercial event.',
  },
  {
    slug: 'domains',
    label: 'Domains',
    description: 'Zylora subdomains, custom DNS, TLS, and route health.',
    emptyTitle: 'No domain is connected',
    emptyDescription: 'Domain setup becomes available for a Website that is ready to publish.',
  },
  {
    slug: 'notifications',
    label: 'Notifications',
    description: 'Durable product and security updates that need your attention.',
    emptyTitle: 'You are all caught up',
    emptyDescription:
      'Important Website, domain, billing, Lead, and security updates will appear here.',
  },
  {
    slug: 'settings',
    label: 'Settings',
    description: 'Account, privacy, locale, security, and active sessions.',
    emptyTitle: 'Account controls are available from this workspace',
    emptyDescription:
      'Profile and privacy settings will use your authenticated account state; they never change ownership or entitlements in the browser.',
  },
];

export const adminSections: PortalSection[] = [
  {
    slug: 'users',
    label: 'Users',
    description: 'Account lifecycle and verified identity state.',
    emptyTitle: 'No User result selected',
    emptyDescription:
      'Search and account operations will use authoritative identity APIs and immutable audit records.',
  },
  {
    slug: 'websites',
    label: 'Websites',
    description: 'Platform-wide Website lifecycle and ownership evidence.',
    emptyTitle: 'No Website result selected',
    emptyDescription:
      'Operational Website records will appear here without bypassing canonical ownership services.',
  },
  {
    slug: 'templates',
    label: 'Templates',
    description: 'Validation, approval, publication, and retirement.',
    emptyTitle: 'Template operations are not connected yet',
    emptyDescription: 'Only validated versions can proceed to approval and publication.',
  },
  {
    slug: 'commerce',
    label: 'Commerce',
    description: 'Plan catalogues, entitlements, subscriptions, invoices, and payments.',
    emptyTitle: 'No commercial operation selected',
    emptyDescription:
      'Prices and capability state will come from versioned backend records, never interface defaults.',
  },
  {
    slug: 'leads-credits',
    label: 'Leads & credits',
    description: 'Lead integrity, credit ledger, and delivery outcomes.',
    emptyTitle: 'No Lead or ledger result selected',
    emptyDescription:
      'Operational records will preserve the one-valid-Lead, one-credit transaction boundary.',
  },
  {
    slug: 'domains',
    label: 'Domains',
    description: 'DNS verification, TLS, routing, and provider health.',
    emptyTitle: 'No domain result selected',
    emptyDescription:
      'Diagnostics will show observed and expected DNS state without exposing provider secrets.',
  },
  {
    slug: 'communications',
    label: 'Content & email',
    description: 'Notifications, campaigns, Blog, and delivery state.',
    emptyTitle: 'No communication selected',
    emptyDescription:
      'Queued, sent, delivered, failed, and suppressed states will remain explicit.',
  },
  {
    slug: 'health',
    label: 'Health',
    description: 'Service readiness, queues, providers, and migration compatibility.',
    emptyTitle: 'Detailed health data is not connected',
    emptyDescription:
      'This screen will report measured system state rather than optimistic green placeholders.',
  },
  {
    slug: 'audit',
    label: 'Audit',
    description: 'Immutable security and privileged-operation evidence.',
    emptyTitle: 'No audit query has run',
    emptyDescription:
      'Filtered audit records will appear here with actor, target, reason, time, and correlation evidence.',
  },
  {
    slug: 'configuration',
    label: 'Configuration',
    description: 'Versioned platform policy and safe provider settings.',
    emptyTitle: 'No configuration group selected',
    emptyDescription:
      'Sensitive values remain in server-side secret management and will never be rendered here.',
  },
];

export function findSection(sections: PortalSection[], slug: string) {
  return sections.find((section) => section.slug === slug);
}
