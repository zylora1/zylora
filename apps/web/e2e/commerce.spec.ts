import { expect, test } from '@playwright/test';

const plans = ['FREE', 'BASIC', 'GROWTH', 'BUSINESS'].map((code, index) => ({
  id: `00000000-0000-0000-0000-00000000000${index + 1}`,
  code,
  name: code[0] + code.slice(1).toLowerCase(),
  description: `${code} monthly plan`,
  slot: index + 1,
  most_popular: code === 'GROWTH',
  price: { amount_minor: [0, 39900, 99900, 199900][index], currency: 'INR' },
  interval: 'MONTHLY',
  entitlements: {
    max_pages: [1, 5, 20, 'UNLIMITED'][index],
    custom_domain: index > 0,
    remove_branding: index > 0,
    ai_monthly_credits: [15, 100, 500, 1500][index],
    whatsapp_monthly_notifications: [0, 150, 750, 2000][index],
    analytics_tier: 'BASIC',
    seo_tier: 'AUTOMATIC_BASIC',
  },
}));

const catalog = {
  region: 'INDIA',
  country_code: 'IN',
  currency: 'INR',
  interval: 'MONTHLY',
  items: plans,
};

test('public pricing is server-catalog driven, monthly-only, and responsive', async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  await page.route('**/api/v1/plans', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(catalog) }),
  );

  await page.goto('/pricing');
  await expect(page.getByRole('heading', { name: /Build freely/i })).toBeVisible();
  await expect(page.getByText('MOST POPULAR')).toBeVisible();
  await expect(page.getByText('₹399')).toBeVisible();
  await expect(page.getByText('₹999')).toBeVisible();
  await expect(page.getByText('₹1,999')).toBeVisible();
  await expect(
    page.getByRole('listitem').filter({ hasText: 'Unlimited Lead capture' }),
  ).toHaveCount(4);
  await expect(page.getByText(/annual/i)).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  expect(consoleErrors).toEqual([]);
});

test('a 30-page Draft evaluates every plan without client-side plan gating', async ({ page }) => {
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ email: 'owner@example.com', account_type: 'USER' }),
    }),
  );
  await page.route('**/api/v1/websites', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            id: 'website-30-pages',
            display_name: 'Thirty-page agency Draft',
            status: 'DRAFT',
            pages: Array.from({ length: 30 }, (_, index) => ({
              id: `page-${index}`,
              name: index === 0 ? 'Home' : `Page ${index}`,
              path: index === 0 ? '/' : `/page-${index}`,
              is_home: index === 0,
              show_in_navigation: index < 8,
            })),
            created_at: '2026-08-01T00:00:00Z',
          },
        ],
      }),
    }),
  );
  await page.route(
    '**/api/v1/websites/website-30-pages/publish-evaluation?domain_type=ZYLORA_SUBDOMAIN',
    (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          website_id: 'website-30-pages',
          page_count: 30,
          domain_type: 'ZYLORA_SUBDOMAIN',
          current_plan_code: 'BUSINESS',
          reuse_existing_subscription: true,
          can_request_publish: true,
          status: 'ELIGIBLE',
          recommended_plan_code: 'BUSINESS',
          plans: plans.map((plan) => ({
            plan,
            eligible: plan.code === 'BUSINESS',
            reasons:
              plan.code === 'BUSINESS'
                ? []
                : [{ code: 'PAGE_LIMIT', detail: `${plan.name} does not support 30 pages.` }],
            is_current_plan: plan.code === 'BUSINESS',
          })),
        }),
      }),
  );

  await page.goto('/app/websites');
  await expect(page.getByRole('heading', { name: 'Thirty-page agency Draft' })).toBeVisible();
  await expect(page.getByText('30 pages')).toBeVisible();
  await page.getByRole('button', { name: 'Check publishing' }).click();
  await expect(page.getByText(/your existing plan will be reused/i)).toBeVisible();
  await expect(page.getByText('Basic does not support 30 pages.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Request publish' })).toBeVisible();
});
