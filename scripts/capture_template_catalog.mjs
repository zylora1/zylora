import { chromium } from '@playwright/test';
import { createHash } from 'node:crypto';
import { access, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { pathToFileURL } from 'node:url';

function option(name, fallback) {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

const baseUrl = option('base-url', 'http://127.0.0.1:3100');
const outputRoot = path.resolve(option('output', 'artifacts/template-visual-audit'));
const requestedLimit = Number(option('limit', '0'));
const forceCapture = process.argv.includes('--force');

async function fileExists(filePath) {
  try {
    await access(filePath);
    return true;
  } catch {
    return false;
  }
}
function safeName(value) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

async function loadCatalogue(request) {
  const items = [];
  let cursor = null;
  do {
    const url = new URL('/api/v1/templates', baseUrl);
    url.searchParams.set('limit', '48');
    if (cursor) url.searchParams.set('cursor', cursor);
    const response = await request.get(url.toString());
    if (!response.ok()) throw new Error(`Catalogue request failed: ${response.status()}`);
    const payload = await response.json();
    items.push(...payload.items);
    cursor = payload.next_cursor;
  } while (cursor);
  const releaseCatalogue = items.filter(
    (item) =>
      ['haven-health', 'atelier-north', 'saffron-table'].includes(item.slug) ||
      item.tags.some((tag) => tag.startsWith('family-')),
  );
  return requestedLimit > 0 ? releaseCatalogue.slice(0, requestedLimit) : releaseCatalogue;
}

function contactSheet(title, records, root) {
  const cards = records
    .map((record) => {
      const desktop = path.relative(root, record.desktop).replaceAll('\\', '/');
      const mobile = path.relative(root, record.mobile).replaceAll('\\', '/');
      return `<article><div><img src="${escapeHtml(desktop)}" alt="${escapeHtml(record.name)} desktop"><img class="mobile" src="${escapeHtml(mobile)}" alt="${escapeHtml(record.name)} mobile"></div><h2>${escapeHtml(record.name)}</h2><p>${escapeHtml(record.category)} · ${escapeHtml(record.family)}</p></article>`;
    })
    .join('');
  return `<!doctype html><html><head><meta charset="utf-8"><style>*{box-sizing:border-box}body{margin:0;background:#080b12;color:#f1f5fa;font:14px/1.4 Arial,sans-serif;padding:28px}header{display:flex;align-items:end;justify-content:space-between;border-bottom:1px solid #293140;padding-bottom:18px}h1{margin:0;font-size:34px;letter-spacing:-.04em}header p{margin:0;color:#8490a4}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-top:18px}article{overflow:hidden;border:1px solid #252d3a;border-radius:12px;background:#111722}article>div{position:relative;aspect-ratio:16/10;overflow:hidden;background:#05080c}img{width:100%;height:100%;object-fit:cover;object-position:top}.mobile{position:absolute;right:8px;bottom:8px;width:22%;height:72%;border:2px solid #111722;border-radius:5px;box-shadow:0 6px 20px #0009}h2{margin:12px 12px 4px;font-size:13px}article p{margin:0 12px 14px;color:#718095;font-size:11px}@media(max-width:1100px){.grid{grid-template-columns:repeat(3,1fr)}}</style></head><body><header><h1>${escapeHtml(title)}</h1><p>${records.length} rendered Templates · desktop + mobile</p></header><div class="grid">${cards}</div></body></html>`;
}

let browser = await chromium.launch();
let context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  reducedMotion: 'reduce',
});

try {
  await mkdir(outputRoot, { recursive: true });
  const catalogue = await loadCatalogue(context.request);
  if (catalogue.length === 0) throw new Error('The approved public Template catalogue is empty.');
  if (requestedLimit === 0 && catalogue.length !== 1_003) {
    throw new Error(`Expected 1,003 release Templates, received ${catalogue.length}.`);
  }
  const records = new Array(catalogue.length);
  let nextIndex = 0;
  let batchEnd = 0;
  let completed = 0;
  async function captureWorker() {
    while (nextIndex < batchEnd) {
      const index = nextIndex;
      nextIndex += 1;
      const item = catalogue[index];
      const family = item.tags.find((tag) => tag.startsWith('family-'))?.slice(7) ?? 'legacy';
      const variant = item.tags.find((tag) => tag.startsWith('voice-'))?.slice(6) ?? 'legacy';
      const category = item.category_slug ?? safeName(item.category);
      const directory = path.join(outputRoot, 'screenshots', safeName(category), safeName(family));
      await mkdir(directory, { recursive: true });
      const desktop = path.join(directory, `${item.slug}-desktop.png`);
      const mobile = path.join(directory, `${item.slug}-mobile.png`);
      const record = {
        name: item.name,
        slug: item.slug,
        category,
        family,
        variant,
        desktop,
        mobile,
      };
      if (!forceCapture && (await fileExists(desktop)) && (await fileExists(mobile))) {
        records[index] = record;
        completed += 1;
        process.stdout.write(`\rRendered ${completed}/${catalogue.length}`);
        continue;
      }
      let captured = false;
      for (let attempt = 1; attempt <= 3 && !captured; attempt += 1) {
        const workerPage = await context.newPage();
        try {
          await workerPage.setViewportSize({ width: 1440, height: 1000 });
          await workerPage.goto(
            `${baseUrl}/templates/${item.slug}/preview?version=${item.version}`,
            {
              waitUntil: 'domcontentloaded',
              timeout: 30_000,
            },
          );
          const frame = workerPage.getByTitle(`${item.name} responsive preview`);
          await frame.waitFor({ state: 'visible', timeout: 15_000 });
          await frame.screenshot({ path: desktop });
          await workerPage.getByRole('button', { name: 'mobile' }).click();
          await frame.screenshot({ path: mobile });
          captured = true;
        } catch (error) {
          if (attempt === 3) throw error;
        } finally {
          await workerPage.close();
        }
      }
      records[index] = record;
      completed += 1;
      process.stdout.write(`\rRendered ${completed}/${catalogue.length}`);
    }
  }
  const captureBatchSize = 50;
  for (let batchStart = 0; batchStart < catalogue.length; batchStart += captureBatchSize) {
    nextIndex = batchStart;
    batchEnd = Math.min(batchStart + captureBatchSize, catalogue.length);
    await Promise.all(Array.from({ length: 4 }, () => captureWorker()));
    await context.close();
    await browser.close();
    if (batchEnd < catalogue.length) {
      browser = await chromium.launch();
      context = await browser.newContext({
        viewport: { width: 1440, height: 1000 },
        reducedMotion: 'reduce',
      });
    }
  }
  process.stdout.write('\n');
  browser = await chromium.launch();
  context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    reducedMotion: 'reduce',
  });

  const groups = new Map();
  for (const record of records) {
    for (const [kind, key] of [
      ['industry', record.category],
      ['family', record.family],
      ['variant', record.variant],
    ]) {
      const id = `${kind}:${key}`;
      groups.set(id, [...(groups.get(id) ?? []), record]);
    }
  }
  const sheetDirectory = path.join(outputRoot, 'contact-sheets');
  await mkdir(sheetDirectory, { recursive: true });
  for (const [id, group] of groups) {
    const [kind, key] = id.split(':');
    const htmlPath = path.join(sheetDirectory, `${safeName(kind)}-${safeName(key)}.html`);
    const pngPath = path.join(sheetDirectory, `${safeName(kind)}-${safeName(key)}.png`);
    await writeFile(htmlPath, contactSheet(`${kind}: ${key}`, group, sheetDirectory), 'utf8');
    const sheetPage = await context.newPage();
    try {
      await sheetPage.setViewportSize({ width: 1440, height: 1000 });
      await sheetPage.goto(pathToFileURL(htmlPath).href, {
        waitUntil: 'domcontentloaded',
        timeout: 30_000,
      });
      await sheetPage.waitForFunction(
        () => Array.from(document.images).every((image) => image.complete),
        undefined,
        { timeout: 90_000 },
      );
      await sheetPage.screenshot({ path: pngPath, fullPage: true });
    } finally {
      await sheetPage.close();
    }
  }

  const exactHashes = new Map();
  for (const record of records) {
    const hash = createHash('sha256')
      .update(await readFile(record.desktop))
      .digest('hex');
    exactHashes.set(hash, [...(exactHashes.get(hash) ?? []), record.slug]);
  }
  const exactDuplicates = [...exactHashes.values()].filter((slugs) => slugs.length > 1);
  const manifest = {
    generated_at: new Date().toISOString(),
    base_url: baseUrl,
    templates: records.length,
    industries: new Set(records.map((record) => record.category)).size,
    families: new Set(records.map((record) => record.family)).size,
    variants: new Set(records.map((record) => record.variant)).size,
    screenshots: records.length * 2,
    exact_duplicate_screenshot_groups: exactDuplicates,
    records,
  };
  await writeFile(path.join(outputRoot, 'manifest.json'), JSON.stringify(manifest, null, 2));
  if (exactDuplicates.length > 0) {
    throw new Error(`Exact duplicate screenshots detected in ${exactDuplicates.length} groups.`);
  }
  console.log(
    `PASS: ${records.length} Templates, ${manifest.families} families, ${manifest.screenshots} screenshots.`,
  );
} finally {
  await browser.close();
}
