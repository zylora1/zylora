import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const document = {
  schema_version: '1.0.0',
  registry_version: '1.0.0',
  metadata: { name: 'Haven Health', description: 'A calm clinic presence.', language: 'en' },
  theme: {
    primary: '#164E46',
    accent: '#E37A5F',
    surface: '#FFFDF8',
    ink: '#17211D',
    heading_font: 'MANROPE',
    body_font: 'INTER',
  },
  assets: [],
  pages: [
    {
      id: 'home-page',
      slug: 'home',
      label: 'Home',
      parent_page_id: null,
      sort_order: 0,
      is_home: true,
      show_in_navigation: true,
      status: 'ACTIVE',
      seo: { title: 'Haven Health', description: 'A calm clinic presence.' },
      components: [
        {
          id: 'hero',
          type: 'HERO',
          props: {
            eyebrow: 'Community clinic',
            heading: 'Thoughtful care, close to home',
            body: 'Care that starts by listening.',
          },
          children: [],
          responsive: {},
          interactions: [],
        },
      ],
    },
  ],
  features: ['LEAD_CAPTURE'],
  requirements: [],
  provenance: 'CURATED',
};
const item = {
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

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/templates**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const body = path.endsWith('/instantiate')
      ? {
          id: '00000000-0000-0000-0000-000000000010',
          owner_user_id: '00000000-0000-0000-0000-000000000020',
          source_template_version_id: '00000000-0000-0000-0000-000000000002',
          display_name: 'Haven Health Draft',
          status: 'DRAFT',
          pages: [
            {
              id: '00000000-0000-0000-0000-000000000030',
              parent_page_id: null,
              name: 'Home',
              slug: '',
              path: '/',
              sort_order: 0,
              is_home: true,
              show_in_navigation: true,
              status: 'DRAFT',
            },
          ],
          created_at: '2026-08-10T00:00:00Z',
          updated_at: '2026-08-10T00:00:00Z',
        }
      : path.endsWith('/preview')
        ? { slug: item.slug, name: item.name, version: 1, document, checksum: 'a'.repeat(64) }
        : path.endsWith('/haven-health')
          ? item
          : { items: [item], next_cursor: null };
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
  });
});

test('approved catalogue filters, details, and cookie-isolated responsive preview work', async ({
  page,
}, testInfo) => {
  await page.goto('/templates');
  await expect(page.getByRole('heading', { name: 'A strong starting point.' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Haven Health' })).toBeVisible();
  await page.getByRole('link', { name: 'View details' }).click();
  await expect(page.getByText(item.summary)).toBeVisible();
  await page.getByRole('link', { name: 'Open responsive preview' }).click();
  const frame = page.frameLocator('iframe[title="Haven Health responsive preview"]');
  await expect(
    frame.getByRole('heading', { name: 'Thoughtful care, close to home' }),
  ).toBeVisible();
  const iframe = page.locator('iframe');
  await expect(iframe).toHaveAttribute('sandbox', '');
  await page.getByRole('button', { name: 'tablet' }).click();
  await expect(iframe).toHaveCSS('width', '768px');
  const isolated = await page.frames()[1]!.evaluate(() => {
    let cookie = 'accessible';
    let storage = 'accessible';
    try {
      void globalThis.document.cookie;
    } catch {
      cookie = 'blocked';
    }
    try {
      localStorage.setItem('x', '1');
    } catch {
      storage = 'blocked';
    }
    return { cookie, storage };
  });
  expect(isolated).toEqual({ cookie: 'blocked', storage: 'blocked' });
  await page.screenshot({
    path: testInfo.outputPath('template-preview-tablet.png'),
    fullPage: true,
  });
});

test('User gallery and isolated Super Admin lifecycle are accessible', async ({ page }) => {
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ email: 'user@example.com', account_type: 'USER' }),
    }),
  );
  await page.goto('/app/templates');
  await expect(page.getByRole('heading', { name: 'Choose your starting point' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Haven Health' })).toBeVisible();
  await page.route('**/api/v1/websites', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            id: '00000000-0000-0000-0000-000000000010',
            display_name: 'Haven Health Draft',
            status: 'DRAFT',
            pages: [
              {
                id: '00000000-0000-0000-0000-000000000030',
                name: 'Home',
                path: '/',
                is_home: true,
                show_in_navigation: true,
              },
            ],
            created_at: '2026-08-10T00:00:00Z',
          },
        ],
      }),
    }),
  );
  await page.getByRole('button', { name: 'Use this Template' }).click();
  await expect(page).toHaveURL('/app/websites');
  await expect(page.getByRole('heading', { name: 'Draft projects' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Haven Health Draft' })).toBeVisible();
  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()).violations,
  ).toEqual([]);

  await page.route('**/api/v1/admin/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ email: 'admin@example.com', account_type: 'SUPER_ADMIN' }),
    }),
  );
  await page.route('**/api/v1/admin/templates', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            ...item,
            status: 'ACTIVE',
            versions: [
              {
                id: '00000000-0000-0000-0000-000000000002',
                version: 1,
                status: 'PUBLISHED',
                checksum: 'a'.repeat(64),
                validation_summary: { valid: true },
                created_at: '2026-08-10T00:00:00Z',
              },
            ],
          },
        ],
      }),
    }),
  );
  await page.goto('http://admin.localhost:3100/admin/templates');
  await expect(page.getByRole('heading', { name: 'Template lifecycle' })).toBeVisible();
  await expect(page.getByText('PUBLISHED')).toBeVisible();
  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()).violations,
  ).toEqual([]);
});
