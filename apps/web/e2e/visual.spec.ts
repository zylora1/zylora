import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const widths = [390, 768, 1024, 1280, 1440] as const;
test.describe.configure({ timeout: 60_000 });

function recordBrowserHealth(page: Page) {
  const consoleProblems: string[] = [];
  const failedRequests: string[] = [];

  page.on('console', (message) => {
    if (message.type() === 'error' || message.type() === 'warning') {
      consoleProblems.push(`${message.type()}: ${message.text()}`);
    }
  });
  page.on('requestfailed', (request) => {
    const failure = request.failure()?.errorText ?? 'failed';
    if (failure === 'net::ERR_ABORTED' && request.url().includes('_rsc=')) return;
    failedRequests.push(`${request.url()}: ${failure}`);
  });

  return { consoleProblems, failedRequests };
}

async function assertViewportHealth(page: Page) {
  const viewport = page.viewportSize();
  expect(viewport).not.toBeNull();
  expect(
    await page.evaluate(() => ({
      documentWidth: document.documentElement.scrollWidth,
      viewportWidth: window.innerWidth,
    })),
  ).toEqual({ documentWidth: viewport?.width, viewportWidth: viewport?.width });

  const accessibility = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
    .analyze();
  expect(accessibility.violations).toEqual([]);
}

test('User portal passes the five-viewport visual and interaction audit', async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== 'desktop-chromium',
    'The audit sets its own exact viewports.',
  );
  const health = recordBrowserHealth(page);
  await page.route('**/api/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ email: 'long.workspace.owner@example.com', account_type: 'USER' }),
    });
  });

  for (const width of widths) {
    await page.setViewportSize({ width, height: width <= 768 ? 900 : 860 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/app');
    await expect(
      page.getByRole('heading', { level: 1, name: 'Publish your first website' }),
    ).toBeVisible();
    await expect(page.getByRole('link', { name: 'Choose a Template' })).toBeVisible();
    await expect(page.getByText('Choose → Customize → Publish')).toBeVisible();
    await assertViewportHealth(page);
    await page.screenshot({ path: testInfo.outputPath(`user-${width}.png`), fullPage: true });

    await page.keyboard.press('Tab');
    await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();

    if (width <= 768) {
      const menu = page.getByRole('button', { name: 'Open navigation' });
      await expect(menu).toBeVisible();
      await menu.focus();
      await menu.click();
      await expect(page.getByRole('navigation', { name: 'User portal navigation' })).toBeVisible();
      await page.screenshot({
        path: testInfo.outputPath(`user-${width}-navigation.png`),
        fullPage: true,
      });
      await page.keyboard.press('Escape');
      await expect(menu).toHaveAttribute('aria-expanded', 'false');
    }
  }

  await page.goto('/app/analytics');
  await page.reload();
  await expect(
    page.getByRole('heading', { name: 'Analytics begins with real traffic' }),
  ).toBeVisible();
  await expect(page.getByText(/zero-value metrics/i)).toBeVisible();
  expect(health.consoleProblems).toEqual([]);
  expect(health.failedRequests).toEqual([]);
});

test('Super Admin passes the five-viewport visual and interaction audit', async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== 'desktop-chromium',
    'The audit sets its own exact viewports.',
  );
  const health = recordBrowserHealth(page);
  await page.route('**/api/v1/admin/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        email: 'primary.super.admin.operations@example.com',
        account_type: 'SUPER_ADMIN',
      }),
    });
  });

  for (const width of widths) {
    await page.setViewportSize({ width, height: width <= 768 ? 900 : 860 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('http://admin.localhost:3100/');
    await expect(page.getByRole('heading', { level: 1, name: 'Platform overview' })).toBeVisible();
    await expect(page.getByText('Loading measured operational state…')).toBeVisible();
    await assertViewportHealth(page);
    await page.screenshot({ path: testInfo.outputPath(`admin-${width}.png`), fullPage: true });

    await page.keyboard.press('Tab');
    await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();

    if (width <= 768) {
      const menu = page.getByRole('button', { name: 'Open navigation' });
      await menu.focus();
      await menu.click();
      await expect(page.getByRole('navigation', { name: 'Super Admin navigation' })).toBeVisible();
      await page.screenshot({
        path: testInfo.outputPath(`admin-${width}-navigation.png`),
        fullPage: true,
      });
      await page.keyboard.press('Escape');
      await expect(menu).toHaveAttribute('aria-expanded', 'false');
    }
  }

  await page.goto('http://admin.localhost:3100/admin/audit');
  await page.reload();
  await expect(page.getByText('No recorded operational state is available yet.')).toBeVisible();
  expect(health.consoleProblems).toEqual([]);
  expect(health.failedRequests).toEqual([]);
});

test('Portal loading and session-expiry states fail closed', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'Covered once in the viewport audit.');
  await page.route('**/api/v1/auth/me', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 400));
    await route.fulfill({ status: 503, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/app');
  await expect(page.getByRole('status', { name: 'Loading workspace' })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('user-loading.png'), fullPage: true });
  await expect(page.getByRole('heading', { name: 'Your session has ended' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login');
  await page.screenshot({ path: testInfo.outputPath('user-session-ended.png'), fullPage: true });
});
