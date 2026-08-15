import { expect, test } from '@playwright/test';

const publicPages = [
  ['/', 'Zylora'],
  ['/website-builder', 'Website Builder'],
  ['/ai-website-builder', 'AI Website Builder'],
  ['/features', 'Features'],
  ['/solutions/small-business', 'Small Business'],
  ['/solutions/freelancers', 'Independent'],
] as const;

test.describe.configure({ timeout: 120_000 });

test('public landing routes expose complete, canonical crawlable HTML', async ({ page }) => {
  for (const [path, titleFragment] of publicPages) {
    const response = await page.goto(path);
    expect(response?.ok(), `${path} should return a successful response`).toBe(true);
    await expect(page).toHaveTitle(new RegExp(titleFragment, 'i'));
    await expect(page.locator('meta[name="description"]')).toHaveAttribute('content', /.{40,}/);
    const canonical = await page.locator('link[rel="canonical"]').getAttribute('href');
    expect(new URL(canonical ?? '').pathname).toBe(path);
    await expect(page.locator('meta[property="og:title"]')).toHaveAttribute('content', /\S+/);
    await expect(page.locator('meta[property="og:description"]')).toHaveAttribute(
      'content',
      /.{40,}/,
    );
    await expect(page.locator('h1')).toHaveCount(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  }
});

test('home remains meaningful when JavaScript is unavailable', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  const response = await page.goto('/');
  expect(response?.ok()).toBe(true);
  await expect(page.getByRole('heading', { level: 1 })).toContainText(
    'Build a professional website',
  );
  await expect(page.getByText('Start with a validated Template')).toBeVisible();
  await expect(page.getByRole('link', { name: /Browse Templates/i }).first()).toBeVisible();
  await context.close();
});

test('structured data and index boundaries remain explicit', async ({ page, request }) => {
  await page.goto('/');
  const graph = await page.locator('script[type="application/ld+json"]').first().textContent();
  expect(graph).toBeTruthy();
  const parsed = JSON.parse(graph ?? '{}') as { '@graph'?: Array<{ '@type'?: string }> };
  expect(parsed['@graph']?.map((entry) => entry['@type'])).toEqual(
    expect.arrayContaining(['Organization', 'WebSite', 'SoftwareApplication', 'FAQPage']),
  );

  for (const path of ['/app', '/admin', '/login', '/templates/example/preview']) {
    const response = await request.get(path, { maxRedirects: 0 });
    expect(response.headers()['x-robots-tag']).toContain('noindex');
  }

  expect((await request.get('/this-route-does-not-exist')).status()).toBe(404);
});

test('scroll-driven scenes transform in full motion and become still in reduced motion', async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== 'desktop-chromium',
    'Full transform audit runs in the desktop project.',
  );
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/');
  const hero = page.locator('section[aria-labelledby="landing-title"]');
  await expect(hero).toHaveAttribute('data-reduced-motion', 'false');
  const layer = hero.locator(':scope > div > div[style]').first();
  const before = await layer.evaluate((node) => getComputedStyle(node).transform);
  await page.evaluate(() => scrollTo({ top: Math.min(850, document.body.scrollHeight / 4) }));
  await page.waitForTimeout(500);
  const after = await layer.evaluate((node) => getComputedStyle(node).transform);
  expect(after).not.toBe(before);

  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.reload();
  await expect(hero).toHaveAttribute('data-reduced-motion', 'true');
  await expect(page.locator('section[aria-labelledby="landing-title"]')).toBeVisible();
});

test('home stays inside local Core Web Vitals release budgets', async ({ page }) => {
  await page.addInitScript(() => {
    const metrics = { cls: 0, lcp: 0, longTaskTotal: 0 };
    Object.defineProperty(window, '__zyloraMetrics', { value: metrics });
    new PerformanceObserver((list) => {
      for (const rawEntry of list.getEntries()) {
        const entry = rawEntry as PerformanceEntry & {
          value?: number;
          hadRecentInput?: boolean;
        };
        if (!entry.hadRecentInput) metrics.cls += entry.value ?? 0;
      }
    }).observe({ type: 'layout-shift', buffered: true });
    new PerformanceObserver((list) => {
      const entries = list.getEntries();
      metrics.lcp = entries.at(-1)?.startTime ?? metrics.lcp;
    }).observe({ type: 'largest-contentful-paint', buffered: true });
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) metrics.longTaskTotal += entry.duration;
    }).observe({ type: 'longtask', buffered: true });
  });

  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.mouse.wheel(0, 900);
  await page.waitForTimeout(1_000);
  const metrics = await page.evaluate(
    () =>
      (
        window as unknown as Window & {
          __zyloraMetrics: { cls: number; lcp: number; longTaskTotal: number };
        }
      ).__zyloraMetrics,
  );
  expect(metrics.lcp).toBeGreaterThan(0);
  expect(metrics.lcp).toBeLessThan(4_000);
  expect(metrics.cls).toBeLessThanOrEqual(0.1);
  expect(metrics.longTaskTotal).toBeLessThan(1_000);
});
