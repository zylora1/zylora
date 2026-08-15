import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const runtime = readFileSync(
  fileURLToPath(
    new URL('../../api/src/zylora_api/modules/publishing/visitor_runtime.js', import.meta.url),
  ),
  'utf8',
);

const publishedMarkup = [
  '<base href="http://127.0.0.1:3100/" />',
  '<button id="manual-contact" type="button" data-zylora-lead-open>Contact us</button>',
  '<section',
  '  data-zylora-lead-controller',
  '  data-auto-delay="10000"',
  '  data-challenge-required="false"',
  '  data-lead-target="contact"',
  '>',
  '  <dialog aria-labelledby="lead-title" data-zylora-lead-dialog>',
  '    <button type="button" aria-label="Close enquiry form" data-zylora-lead-close>Close</button>',
  '    <h2 id="lead-title">Send an enquiry</h2>',
  '    <form data-zylora-lead-form>',
  '      <label>Name <input name="name" required /></label>',
  '      <label>Email <input name="email" type="email" /></label>',
  '      <label>Phone <input name="phone" /></label>',
  '      <label>Enquiry <textarea name="enquiry" required></textarea></label>',
  '      <label><input name="contact_consent" type="checkbox" /> Contact consent</label>',
  '      <input name="turnstile_token" type="hidden" />',
  '      <button type="submit">Send enquiry</button>',
  '      <p role="status" data-zylora-lead-status></p>',
  '    </form>',
  '    <section hidden tabindex="-1" data-zylora-lead-success>',
  '      <h3>Thank you</h3>',
  '    </section>',
  '  </dialog>',
  '</section>',
  '<aside class="zylora-chatbot">',
  '  <button type="button" aria-expanded="false" class="zylora-chatbot__open">Ask a question</button>',
  '  <section hidden class="zylora-chatbot__panel">',
  '    <div aria-live="polite" class="zylora-chatbot__messages"></div>',
  '    <form class="zylora-chatbot__form">',
  '      <label>Question <input name="message" /></label>',
  '      <button type="submit">Send</button>',
  '    </form>',
  '    <button type="button" data-zylora-lead-open>Send an enquiry</button>',
  '  </section>',
  '</aside>',
].join('\n');

test('chatbot remains Q&A-only and automatic dismissal is session-capped', async ({ page }) => {
  await page.goto('/health');
  await page.clock.install();
  let leadRequests = 0;
  let messageRequests = 0;
  await page.route('**/api/v1/public/leads', async (route) => {
    leadRequests += 1;
    await route.fulfill({ status: 500 });
  });
  await page.route('**/api/v1/public/chatbot/conversations', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ id: 'conversation-1', access_token: 'opaque-capability' }),
    });
  });
  await page.route('**/api/v1/public/chatbot/conversations/*/messages', async (route) => {
    messageRequests += 1;
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ answer: 'We are open Monday to Friday.' }),
    });
  });

  await page.setContent(publishedMarkup);
  await page.addScriptTag({ content: runtime });
  const dialog = page.locator('[data-zylora-lead-dialog]');

  await page.getByRole('button', { name: 'Ask a question' }).click();
  await page.getByLabel('Question').fill('When are you open?');
  await page.locator('.zylora-chatbot__form').getByRole('button', { name: 'Send' }).click();
  await expect(page.getByText('We are open Monday to Friday.')).toBeVisible();
  expect(messageRequests).toBe(1);
  expect(leadRequests).toBe(0);

  await page.getByRole('button', { name: 'Ask a question' }).click();
  await page.clock.fastForward(10_000);
  await expect(dialog).toBeVisible();

  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect
    .poll(() => page.evaluate(() => sessionStorage.getItem('zylora.lead-form.dismissed')))
    .toBe('true');
  await page.clock.fastForward(60_000);
  await expect(dialog).not.toBeVisible();

  await page.getByRole('button', { name: 'Contact us' }).click();
  await expect(dialog).toBeVisible();
  expect(leadRequests).toBe(0);
});

test('only an explicit form submission creates a form-sourced lead and caps the session', async ({
  page,
}) => {
  await page.goto('/health');
  await page.clock.install();
  const submissions: Array<Record<string, unknown>> = [];
  await page.route('**/api/v1/public/leads', async (route) => {
    submissions.push(route.request().postDataJSON() as Record<string, unknown>);
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ id: 'lead-1', source: 'FORM', duplicate: false }),
    });
  });

  await page.setContent(publishedMarkup);
  await page.addScriptTag({ content: runtime });
  await page.clock.fastForward(10_000);
  const dialog = page.locator('[data-zylora-lead-dialog]');
  await expect(dialog).toBeVisible();

  await page.getByLabel('Name').fill('Ada Visitor');
  await page.getByLabel('Email').fill('ada@example.com');
  await page.locator('textarea[name="enquiry"]').fill('Please send the service guide.');
  await page.getByLabel('Contact consent').check();
  await page.getByRole('button', { name: 'Send enquiry' }).click();

  await expect(page.getByRole('heading', { name: 'Thank you' })).toBeVisible();
  expect(submissions).toHaveLength(1);
  expect(submissions[0]).toMatchObject({
    name: 'Ada Visitor',
    email: 'ada@example.com',
    enquiry: 'Please send the service guide.',
    consent: { contact: true },
  });
  expect(JSON.stringify(submissions[0])).not.toContain('chatbot');
  await expect
    .poll(() => page.evaluate(() => sessionStorage.getItem('zylora.lead-form.submitted')))
    .toBe('true');

  await page.evaluate(() => {
    const formDialog = document.querySelector('[data-zylora-lead-dialog]');
    if (formDialog instanceof HTMLDialogElement) formDialog.close();
  });
  await page.clock.fastForward(60_000);
  await expect(dialog).not.toBeVisible();
  expect(submissions).toHaveLength(1);
});
