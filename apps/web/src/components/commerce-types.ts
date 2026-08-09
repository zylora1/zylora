export type EntitlementValue = boolean | number | string;

export type Money = {
  amount_minor: number;
  currency: 'INR' | 'USD';
};

export type Plan = {
  id: string;
  code: 'FREE' | 'BASIC' | 'GROWTH' | 'BUSINESS';
  name: string;
  description: string;
  slot: number;
  most_popular: boolean;
  price: Money;
  interval: 'MONTHLY';
  entitlements: Record<string, EntitlementValue>;
};

export type PlanCatalog = {
  region: 'INDIA' | 'INTERNATIONAL';
  country_code: string;
  currency: 'INR' | 'USD';
  interval: 'MONTHLY';
  items: Plan[];
};

export type Subscription = {
  plan_code: string;
  state: string;
  is_paid: boolean;
  price: Money;
  interval: 'MONTHLY';
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  entitlements: Record<string, EntitlementValue>;
};

export type PublishEvaluation = {
  website_id: string;
  page_count: number;
  domain_type: 'ZYLORA_SUBDOMAIN' | 'CUSTOM';
  current_plan_code: string;
  reuse_existing_subscription: boolean;
  can_request_publish: boolean;
  status: 'ELIGIBLE' | 'UPGRADE_REQUIRED' | 'INELIGIBLE';
  recommended_plan_code: string | null;
  plans: Array<{
    plan: Plan;
    eligible: boolean;
    reasons: Array<{ code: string; detail: string }>;
    is_current_plan: boolean;
  }>;
};

export function formatMoney(money: Money): string {
  return new Intl.NumberFormat(money.currency === 'INR' ? 'en-IN' : 'en-US', {
    style: 'currency',
    currency: money.currency,
    maximumFractionDigits: 0,
  }).format(money.amount_minor / 100);
}

export function planFeatures(plan: Plan): string[] {
  const entitlements = plan.entitlements;
  const pages =
    entitlements.max_pages === 'UNLIMITED'
      ? 'Unlimited published pages'
      : `Up to ${String(entitlements.max_pages)} published ${entitlements.max_pages === 1 ? 'page' : 'pages'}`;
  const domain = entitlements.custom_domain ? 'Custom domain included' : 'Zylora subdomain only';
  const branding = entitlements.remove_branding
    ? 'Zylora branding removed'
    : 'Zylora branding included';
  const analytics = String(entitlements.analytics_tier).replaceAll('_', ' ').toLowerCase();
  const seo = String(entitlements.seo_tier).replaceAll('_', ' ').toLowerCase();
  return [
    pages,
    domain,
    branding,
    `${String(entitlements.ai_monthly_credits)} AI credits / month`,
    'Unlimited Lead capture',
    `${String(entitlements.whatsapp_monthly_notifications)} WhatsApp notifications / month`,
    `${analytics} analytics`,
    `${seo} SEO`,
  ];
}
