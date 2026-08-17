import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

function websiteFixture(count: number) {
  const now = '2026-08-11T00:00:00Z';
  const pages = Array.from({ length: count }, (_, index) => {
    const isHome = index === 0;
    const groupRoot = index ? index - ((index - 1) % 10) : 0;
    const parentIndex = isHome || index % 10 === 1 ? null : groupRoot;
    return {
      id: `page-${index}`,
      parent_page_id: parentIndex ? `page-${parentIndex}` : null,
      name: isHome ? 'Home' : `Page ${index}`,
      slug: isHome ? '' : `page-${index}`,
      path: isHome ? '/' : `${parentIndex ? `/page-${parentIndex}` : ''}/page-${index}`,
      sort_order: index % 10,
      is_home: isHome,
      show_in_navigation: index % 5 !== 0,
      status: 'DRAFT',
      seo: {},
      created_at: now,
      updated_at: now,
    };
  });
  return {
    id: 'website-1',
    owner_user_id: 'user-1',
    source_template_version_id: 'template-version-1',
    display_name: 'Atlas Directory Draft',
    status: 'DRAFT',
    site_origin: 'AI',
    pages,
    navigation: pages
      .filter((page) => page.parent_page_id === null && page.show_in_navigation)
      .map((page) => ({
        page_id: page.id,
        label: page.name,
        path: page.path,
        children: [],
      })),
    path_changes: [],
    created_at: now,
    updated_at: now,
  };
}

test('100-page Website map stays compact, accessible, mutable, and plan-free', async ({
  page,
}, testInfo) => {
  let website = websiteFixture(100);
  await page.route(/\/api\/v1\/auth\/me$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ email: 'owner@example.com', account_type: 'USER' }),
    }),
  );
  await page.route(/\/api\/v1\/websites\/website-1/, async (route) => {
    const request = route.request();
    const method = request.method();
    const path = new URL(request.url()).pathname;
    if (method === 'PATCH') {
      const pageId = path.split('/').at(-1);
      const patch = request.postDataJSON();
      website = {
        ...website,
        pages: website.pages.map((item) =>
          item.id === pageId ? { ...item, ...patch, updated_at: '2026-08-11T00:01:00Z' } : item,
        ),
        path_changes: [],
      };
    } else if (method === 'POST') {
      const payload = request.postDataJSON();
      website = {
        ...website,
        pages: [
          ...website.pages,
          {
            id: 'campaign-page',
            ...payload,
            path: `/${payload.slug}`,
            sort_order: 99,
            is_home: false,
            status: 'DRAFT',
            seo: {},
            created_at: '2026-08-11T00:01:00Z',
            updated_at: '2026-08-11T00:01:00Z',
          },
        ],
        path_changes: [],
      };
    } else if (method === 'DELETE') {
      const pageId = path.split('/').at(-1);
      website = {
        ...website,
        pages: website.pages.filter((item) => item.id !== pageId),
        path_changes: [],
      };
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(website),
    });
  });

  await page.goto('/app/websites/website-1/edit');
  await expect(page.getByRole('heading', { name: 'Atlas Directory Draft' })).toBeVisible();
  await expect(page.getByText('100 pages', { exact: true })).toBeVisible();
  await expect(page.getByText('No plan required')).toBeVisible();
  await expect(page.getByRole('tree', { name: 'Website page hierarchy' })).toBeVisible();

  const treeViewport = page.getByRole('tree').locator('..');
  expect(
    await treeViewport.evaluate((element) => element.scrollHeight > element.clientHeight),
  ).toBe(true);

  await page.getByRole('button', { name: 'Collapse Page 1', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Open Page 2', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Expand Page 1', exact: true }).click();

  await page.getByLabel('Search pages').fill('page-99');
  await expect(page.getByText('1 of 100 pages')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Open Page 99', exact: true })).toBeVisible();
  await page.getByLabel('Search pages').clear();

  await page.getByRole('button', { name: 'Open Page 2', exact: true }).click();
  await page.getByLabel('Page name').fill('SEO Services');
  await page.getByLabel('Show in primary navigation').uncheck();
  await page.getByRole('button', { name: 'Save page settings' }).click();
  await expect(page.getByText('Page settings saved. Navigation was regenerated.')).toBeVisible();

  await page.getByRole('button', { name: 'Add page' }).click();
  await page.getByLabel('Page name').fill('Campaign Summer');
  await page.getByLabel(/URL slug/).fill('campaign-summer');
  await page.getByRole('button', { name: 'Add page', exact: true }).last().click();
  await expect(page.getByRole('heading', { name: 'Campaign Summer' })).toBeVisible();

  await expect(page.getByText(/collaborator|team member|editing now/i)).toHaveCount(0);
  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()).violations,
  ).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath('page-manager-100-pages.png'),
    fullPage: true,
  });
});
