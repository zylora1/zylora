import { expect, test } from '@playwright/test';

const projectId = '019ff9d0-1578-7dc7-8c1f-fff23b2f4904';
const generationId = 'dd86f0e6-e1c2-4629-8ae9-6817234eaba6';

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/auth/challenge/config', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ enabled: false, site_key: null }),
    });
  });
  await page.route('**/api/v1/plans', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        region: 'INTERNATIONAL',
        country_code: 'ZZ',
        currency: 'USD',
        interval: 'MONTHLY',
        items: [],
      }),
    });
  });
});
function project(status: 'QUEUED' | 'COMPLETED') {
  return {
    id: projectId,
    status,
    generation_id: generationId,
    generation_version: 1,
    attempt: status === 'COMPLETED' ? 1 : 0,
    max_attempts: 4,
    retryable: false,
    can_cancel: status === 'QUEUED',
    can_retry: false,
    preview_ready: status === 'COMPLETED',
    artifact_digest: status === 'COMPLETED' ? 'a'.repeat(64) : null,
    safe_error_code: null,
    safe_error_message: null,
    queued_at: '2026-08-13T06:00:00Z',
    started_at: status === 'COMPLETED' ? '2026-08-13T06:00:05Z' : null,
    completed_at: status === 'COMPLETED' ? '2026-08-13T06:01:00Z' : null,
    failed_at: null,
    cancelled_at: null,
    created_at: '2026-08-13T06:00:00Z',
    updated_at: '2026-08-13T06:01:00Z',
  };
}

test('AI prompt continues through authentication and durable state survives refresh', async ({
  page,
}) => {
  let accepted = false;
  let restored = false;
  const prompt = 'A premium dental clinic website with treatments, doctors, FAQs, and enquiries.';

  await page.route('**/api/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ email: 'owner@example.com', account_type: 'USER' }),
    });
  });
  await page.route('**/api/v1/ai-site-projects', async (route) => {
    const request = route.request();
    if (request.method() === 'POST') {
      expect(request.headers()['x-csrf-token']).toBe('ai-e2e-csrf');
      expect(request.headers()['idempotency-key']).toMatch(/^ai-site-/);
      expect(request.postDataJSON()).toEqual({ prompt });
      accepted = true;
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify(project('QUEUED')),
      });
      return;
    }
    const items = accepted ? [project(restored ? 'COMPLETED' : 'QUEUED')] : [];
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items }),
    });
  });

  await page.goto('/');
  await page.getByLabel('Describe the website you want to build').fill(prompt);
  await page.getByRole('button', { name: 'Build this website with AI' }).click();
  await expect(page).toHaveURL(/\/signup\?intent=ai$/);

  await page
    .context()
    .addCookies([{ name: 'zylora_user_csrf', value: 'ai-e2e-csrf', url: 'http://127.0.0.1:3100' }]);
  await page.goto('/app/ai-builder');
  await expect(page.getByLabel('What should this website accomplish?')).toHaveValue(prompt);
  await page.getByRole('button', { name: 'Build this website' }).click();
  await expect(page.getByText('Queued', { exact: true })).toBeVisible();
  await expect(page.getByRole('status')).toContainText('leave or refresh this page safely');

  restored = true;
  await page.reload();
  await expect(page.getByText('Preview ready', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Open artifact' })).toBeVisible();
  await expect(page.getByText(/attempt 1 of 4/)).toBeVisible();
});

test('AI Builder displays the server-authoritative disabled response', async ({ page }) => {
  await page.route('**/api/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ email: 'owner@example.com', account_type: 'USER' }),
    });
  });
  await page.route('**/api/v1/ai-site-projects', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 503,
        contentType: 'application/problem+json',
        body: JSON.stringify({ detail: 'AI website generation is not available right now.' }),
      });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{"items":[]}' });
  });

  await page.goto('/app/ai-builder');
  await page
    .getByLabel('What should this website accomplish?')
    .fill('A professional website for a local architecture and design studio.');
  await page.getByRole('button', { name: 'Build this website' }).click();
  await expect(
    page.getByText('AI website generation is not available right now.', { exact: true }),
  ).toHaveText('AI website generation is not available right now.');
  await expect(page.getByText(/No AI website projects yet/)).toBeVisible();
});
