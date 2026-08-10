import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/auth/challenge/config', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ enabled: false, site_key: null }),
    });
  });
});

test('identity entry and health surfaces are responsive and hardened', async ({
  page,
  request,
}) => {
  const consoleErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });

  await page.goto('/');
  await expect(
    page.getByRole('heading', { level: 1, name: 'Choose the shape. Make it unmistakably yours.' }),
  ).toBeVisible();
  await expect(page.getByRole('link', { name: 'Explore Templates' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );

  const health = await request.get('/health');
  expect(health.ok()).toBe(true);
  expect(health.headers()).toMatchObject({
    'cache-control': 'private, no-store',
    'cross-origin-opener-policy': 'same-origin',
    'x-content-type-options': 'nosniff',
    'x-frame-options': 'DENY',
    'x-robots-tag': 'noindex, nofollow',
  });
  expect(consoleErrors).toEqual([]);
});

test('User auth exposes safe errors, recovery, and verification navigation', async ({ page }) => {
  await page.route('**/api/v1/auth/challenge/config', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ enabled: true, site_key: '1x00000000000000000000AA' }),
    });
  });
  await page.route(
    'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit',
    async (route) => {
      await route.fulfill({
        contentType: 'application/javascript',
        body: `window.turnstile={render:function(_element,options){setTimeout(function(){options.callback('e2e-single-use-token')},0);return 'e2e-widget'},remove:function(){}};`,
      });
    },
  );
  await page.route('**/api/v1/auth/login', async (route) => {
    expect(route.request().postDataJSON()).toMatchObject({
      turnstile_token: 'e2e-single-use-token',
    });
    await route.fulfill({
      status: 401,
      contentType: 'application/problem+json',
      body: JSON.stringify({ detail: 'Email or password is incorrect.' }),
    });
  });
  await page.goto('/login');
  await page.getByLabel('Email address').fill('person@example.com');
  await page.getByLabel('Password').fill('Wrong-Password-42!');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.locator('.form-message--error')).toHaveText('Email or password is incorrect.');

  await page.goto('/login?oauth_error=cancelled');
  await expect(page.locator('.form-message--error')).toHaveText(
    'Google sign-in could not be completed. Please try again.',
  );

  await page.unroute('**/api/v1/auth/login');
  await page.route('**/api/v1/auth/signup', async (route) => {
    await route.fulfill({ status: 202, contentType: 'application/json', body: '{}' });
  });
  await page.goto('/signup');
  await page.getByLabel('Email address').fill('person@example.com');
  await page.locator('input[name="password"]').fill('Strong-Password-42!');
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page).toHaveURL(/\/verify-email\?email=person%40example\.com$/);
  await expect(page.getByRole('heading', { name: 'Verify your email' })).toBeVisible();
});

test('Super Admin application is absent on the User host and present on its isolated host', async ({
  page,
}) => {
  const userHostResponse = await page.goto('/admin/login');
  expect(userHostResponse?.status()).toBe(404);

  await page.goto('http://admin.localhost:3100/login');
  await expect(page.getByRole('heading', { name: 'Super Admin sign in' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Enter administration' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Continue with Google' })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
});
