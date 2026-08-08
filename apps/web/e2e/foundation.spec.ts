import { expect, test } from '@playwright/test';

test('foundation page and Web health endpoint are operational', async ({ page, request }) => {
  const consoleErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });

  await page.goto('/');
  await expect(page.getByRole('main')).toBeVisible();
  await expect(page.getByRole('heading', { level: 1, name: 'Platform foundation' })).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );

  const health = await request.get('/health');
  expect(health.ok()).toBe(true);
  await expect(health.json()).resolves.toMatchObject({ service: 'zylora-web', status: 'alive' });
  expect(health.headers()).toMatchObject({
    'referrer-policy': 'strict-origin-when-cross-origin',
    'x-content-type-options': 'nosniff',
    'x-frame-options': 'DENY',
  });
  expect(consoleErrors).toEqual([]);
});
