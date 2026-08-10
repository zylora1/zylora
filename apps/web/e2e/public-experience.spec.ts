import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const template = {
  id: '00000000-0000-0000-0000-000000000001',
  slug: 'haven-health',
  name: 'Haven Health',
  summary: 'A calm, trust-first clinic presence with a clear enquiry path.',
  category: 'Health & Wellness',
  category_slug: 'health-wellness',
  tags: ['calm', 'clinic'],
  features: ['LEAD_CAPTURE'],
  version: 1,
  status: 'PUBLISHED',
  featured_order: 10,
};

async function assertNoHorizontalOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/auth/challenge/config', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ enabled: false, site_key: null }),
    }),
  );
  await page.route('**/api/v1/templates**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(pathname.endsWith('/haven-health') ? template : { items: [template] }),
    });
  });
  await page.route('**/api/v1/blog/posts', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) }),
  );
});

test('public marketing pages remain polished, responsive, and accessible', async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== 'desktop-chromium',
    'The audit sets exact desktop and mobile viewports.',
  );

  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');
    await expect(
      page.getByRole('heading', {
        level: 1,
        name: 'Choose the shape. Make it unmistakably yours.',
      }),
    ).toBeVisible();
    await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Start building' })).toBeVisible();
    await assertNoHorizontalOverflow(page);
    expect(
      (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
        .violations,
    ).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath(`landing-${width}.png`), fullPage: true });
  }

  await page.goto('/templates/haven-health');
  await expect(page.getByRole('heading', { name: 'Haven Health' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible();
  await assertNoHorizontalOverflow(page);

  await page.goto('/blog');
  await expect(
    page.getByRole('heading', { name: 'Clear thinking for considered websites.' }),
  ).toBeVisible();
  await expect(page.getByText('No articles have been published yet.')).toBeVisible();
});

test('public contact gives accessible confirmation and keeps the server command narrow', async ({
  page,
}) => {
  await page.route('**/api/v1/public/contact', async (route) => {
    expect(route.request().postDataJSON()).toEqual({
      name: 'Ada Lovelace',
      email: 'ada@example.com',
      message: 'Please help us select an approved Template.',
      turnstile_token: null,
    });
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'accepted', id: 'opaque-contact-id' }),
    });
  });

  await page.goto('/contact');
  await page.getByLabel('Name').fill('Ada Lovelace');
  await page.getByLabel('Email').fill('ada@example.com');
  await page.getByLabel('Message').fill('Please help us select an approved Template.');
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByRole('status')).toContainText('safely queued');
  await assertNoHorizontalOverflow(page);
});

test('public index controls enumerate intended pages and exclude private routes', async ({
  request,
}) => {
  const robots = await request.get('/robots.txt');
  expect(robots.ok()).toBe(true);
  expect(await robots.text()).toContain('Disallow: /app/');
  expect(await robots.text()).toContain('Disallow: /admin/');

  const sitemap = await request.get('/sitemap.xml');
  expect(sitemap.ok()).toBe(true);
  expect(await sitemap.text()).toContain('/templates');
  expect(await sitemap.text()).not.toContain('/app/');
});
