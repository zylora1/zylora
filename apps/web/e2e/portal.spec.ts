import { expect, test } from '@playwright/test';

test('User portal presents the first-use path and stable responsive navigation', async ({
  page,
}) => {
  const consoleErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  await page.route('**/api/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ email: 'person@example.com', account_type: 'USER' }),
    });
  });

  const response = await page.goto('/app');
  expect(response?.headers()['x-robots-tag']).toBe('noindex, nofollow');
  await expect(
    page.getByRole('heading', { level: 1, name: 'Publish your first website' }),
  ).toBeVisible();
  await expect(page.getByText('Choose → Customize → Publish')).toBeVisible();

  if ((page.viewportSize()?.width ?? 1280) < 768) {
    await page.getByRole('button', { name: 'Open navigation' }).click();
  }
  const navigation = page.getByRole('navigation', { name: 'User portal navigation' });
  await expect(navigation).toBeVisible();
  await navigation.getByRole('link', { name: 'Analytics' }).click();
  await expect(page).toHaveURL(/\/app\/analytics$/);
  await expect(
    page.getByRole('heading', { name: 'Analytics begins with real traffic' }),
  ).toBeVisible();
  await expect(page.getByText(/zero-value metrics/i)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  expect(consoleErrors).toEqual([]);
});

test('Super Admin console remains isolated and evidence-led', async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  await page.route('**/api/v1/admin/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ email: 'operator@example.com', account_type: 'SUPER_ADMIN' }),
    });
  });

  const response = await page.goto('http://admin.localhost:3100/');
  expect(response?.headers()['x-robots-tag']).toBe('noindex, nofollow');
  await expect(page.getByRole('heading', { level: 1, name: 'Platform overview' })).toBeVisible();
  await expect(page.getByText('Loading measured operational state…')).toBeVisible();

  if ((page.viewportSize()?.width ?? 1280) < 768) {
    await page.getByRole('button', { name: 'Open navigation' }).click();
  }
  const navigation = page.getByRole('navigation', { name: 'Super Admin navigation' });
  await navigation.getByRole('link', { name: 'Audit' }).click();
  await expect(page).toHaveURL(/\/admin\/audit$/);
  await expect(page.getByText('No recorded operational state is available yet.')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  expect(consoleErrors).toEqual([]);
});
