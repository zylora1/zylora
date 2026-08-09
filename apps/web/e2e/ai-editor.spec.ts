import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const pageId = '12345678-1234-4567-89ab-1234567890ab';
const documentPageId = `p${pageId.replaceAll('-', '')}`;

function document() {
  return {
    schema_version: '1.0.0',
    registry_version: '1.0.0',
    metadata: { name: 'Studio Draft', description: 'AI editor E2E.', language: 'en' },
    theme: {
      primary: '#5B5BD6',
      accent: '#27C499',
      surface: '#FFFFFF',
      ink: '#171A2B',
      heading_font: 'MANROPE',
      body_font: 'INTER',
    },
    assets: [],
    pages: [
      {
        id: documentPageId,
        slug: 'home',
        label: 'Home',
        parent_page_id: null,
        sort_order: 0,
        is_home: true,
        show_in_navigation: true,
        status: 'ACTIVE',
        seo: { title: 'Home', description: 'Studio home.' },
        components: [
          {
            id: 'hero-home',
            type: 'HERO',
            props: {
              heading: 'A precise first impression',
              body: 'Built from a validated Template.',
            },
            children: [],
            responsive: {},
            interactions: [],
          },
        ],
      },
    ],
    features: [],
    requirements: [],
    provenance: 'CURATED',
  };
}

test('manual and AI edits share the document, credits, responsive preview, and restore', async ({
  page,
}) => {
  const now = '2026-08-12T00:00:00Z';
  let revision = 1;
  let credits = 15;
  let revisions = [
    {
      id: 'revision-1',
      revision: 1,
      source: 'TEMPLATE',
      edit_summary: 'Created from template',
      created_at: now,
    },
  ];
  const website = {
    id: 'website-1',
    display_name: 'Studio Draft',
    status: 'DRAFT',
    revision,
    pages: [
      {
        id: pageId,
        parent_page_id: null,
        name: 'Home',
        slug: '',
        path: '/',
        sort_order: 0,
        is_home: true,
        show_in_navigation: true,
        status: 'DRAFT',
        seo: {},
        created_at: now,
        updated_at: now,
      },
    ],
    navigation: [{ page_id: pageId, label: 'Home', path: '/', children: [] }],
    path_changes: [],
  };
  const editorState = () => ({
    website_id: 'website-1',
    display_name: 'Studio Draft',
    status: 'DRAFT',
    revision,
    document: document(),
    revisions,
    credits: {
      balance: credits,
      allowance: 15,
      period_start: now,
      period_end: '2026-09-01T00:00:00Z',
    },
  });

  await page.route(/\/api\/v1\/auth\/me$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ email: 'owner@example.com', account_type: 'USER' }),
    }),
  );
  await page.route(/\/api\/v1\/websites\/website-1$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(website) }),
  );
  await page.route(/\/api\/v1\/websites\/website-1\/editor(?:\/.*)?$/, async (route) => {
    const request = route.request();
    let source = 'MANUAL';
    let summary = 'Heading autosaved';
    let used = 0;
    if (request.method() === 'POST') {
      revision += 1;
      if (request.url().endsWith('/ai-edits')) {
        source = 'AI';
        summary = 'Added FAQ under Resources';
        credits -= 1;
        used = 1;
      } else if (request.url().includes('/restore')) {
        source = 'RESTORE';
        summary = 'Restored revision 1';
      }
      revisions = [
        { id: `revision-${revision}`, revision, source, edit_summary: summary, created_at: now },
        ...revisions,
      ];
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ...editorState(),
        operation_id: 'operation-1',
        source,
        summary,
        credits_used: used,
      }),
    });
  });

  await page.goto('/app/websites/website-1/edit');
  await page.getByRole('button', { name: 'Content & AI' }).click();
  await expect(page.getByRole('heading', { name: 'Studio Draft' })).toBeVisible();
  await expect(page.getByText('15 AI credits')).toBeVisible();

  await page.getByLabel('heading').fill('A more confident first impression');
  await page.getByLabel('heading').blur();
  await expect(page.locator('div').filter({ hasText: /^Heading autosaved$/ })).toBeVisible();
  await expect(page.getByText('Revision 2', { exact: true }).first()).toBeVisible();

  await page.getByLabel('Change scope').selectOption('WEBSITE');
  await page
    .getByLabel('Tell Zylora what to change')
    .fill('Add an FAQ page under Resources and add it to navigation.');
  await page.getByRole('button', { name: 'Plan and apply change' }).click();
  await expect(page.getByText(/Added FAQ under Resources · 1 credit used/)).toBeVisible();
  await expect(page.getByText('14 AI credits')).toBeVisible();

  await page.getByRole('button', { name: 'mobile preview' }).click();
  await expect(page.getByRole('button', { name: 'mobile preview' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await page.getByRole('button', { name: 'Restore revision 1' }).click();
  await expect(page.locator('div').filter({ hasText: /^Restored revision 1$/ })).toBeVisible();

  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()).violations,
  ).toEqual([]);
});
