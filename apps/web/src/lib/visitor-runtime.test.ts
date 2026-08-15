import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const repositoryRoot = process.cwd().replace(/[\\/]apps[\\/]web$/, '');
const runtime = readFileSync(
  resolve(repositoryRoot, 'apps/api/src/zylora_api/modules/publishing/visitor_runtime.js'),
  'utf8',
);

function markup() {
  return `
    <button type="button" data-zylora-lead-open>Contact us</button>
    <div data-zylora-lead-controller data-auto-delay="10000" data-lead-target="contact" data-challenge-required="false">
      <dialog data-zylora-lead-dialog aria-labelledby="lead-title">
        <button type="button" data-zylora-lead-close>Close</button>
        <form data-zylora-lead-form>
          <h2 id="lead-title">Send an enquiry</h2>
          <input name="name" required />
          <input name="email" />
          <input name="phone" />
          <textarea name="enquiry" required></textarea>
          <input name="contact_consent" type="checkbox" />
          <input name="turnstile_token" type="hidden" />
          <p data-zylora-lead-status></p>
          <button type="submit">Send</button>
        </form>
        <div data-zylora-lead-success tabindex="-1" hidden>Thank you</div>
      </dialog>
    </div>
  `;
}

function installDialog() {
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', {
    configurable: true,
    value(this: HTMLDialogElement) {
      this.open = true;
      this.setAttribute('open', '');
    },
  });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', {
    configurable: true,
    value(this: HTMLDialogElement) {
      this.open = false;
      this.removeAttribute('open');
      this.dispatchEvent(new Event('close'));
    },
  });
}

function runRuntime() {
  window.eval(runtime);
  const root = document.querySelector<HTMLElement>('[data-zylora-lead-controller]');
  if (root && root.dataset.ready !== 'true') {
    document.dispatchEvent(new Event('DOMContentLoaded'));
  }
}

function dialog() {
  return document.querySelector<HTMLDialogElement>('[data-zylora-lead-dialog]')!;
}

describe('published visitor lead-capture runtime', () => {
  let visibility: DocumentVisibilityState;

  beforeEach(() => {
    vi.useFakeTimers();
    sessionStorage.clear();
    document.body.innerHTML = markup();
    visibility = 'visible';
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      get: () => visibility,
    });
    installDialog();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
    document.body.innerHTML = '';
  });

  it('does not auto-open before ten visible seconds and opens after the minimum delay', () => {
    runRuntime();

    vi.advanceTimersByTime(9_999);
    expect(dialog().open).toBe(false);

    vi.advanceTimersByTime(1);
    expect(dialog().open).toBe(true);
    expect(document.activeElement).toBe(document.querySelector('input[name="name"]'));
  });

  it('pauses eligibility while hidden and resumes only after ten visible seconds', () => {
    runRuntime();
    vi.advanceTimersByTime(4_000);
    visibility = 'hidden';
    document.dispatchEvent(new Event('visibilitychange'));

    vi.advanceTimersByTime(20_000);
    expect(dialog().open).toBe(false);

    visibility = 'visible';
    document.dispatchEvent(new Event('visibilitychange'));
    vi.advanceTimersByTime(5_999);
    expect(dialog().open).toBe(false);
    vi.advanceTimersByTime(1);
    expect(dialog().open).toBe(true);
  });

  it('does nothing when the published Website has no enabled lead form', () => {
    document.body.innerHTML = '<button class="zylora-chatbot__open">Chat</button>';
    expect(() => runRuntime()).not.toThrow();
    vi.advanceTimersByTime(20_000);
    expect(document.querySelector('[data-zylora-lead-dialog]')).toBeNull();
  });

  it('caps automatic display after dismissal but still permits a manual CTA', () => {
    runRuntime();
    vi.advanceTimersByTime(10_000);
    expect(dialog().open).toBe(true);

    document.querySelector<HTMLButtonElement>('[data-zylora-lead-close]')!.click();
    expect(dialog().open).toBe(false);
    expect(sessionStorage.getItem('zylora.lead-form.dismissed')).toBe('true');

    vi.advanceTimersByTime(60_000);
    expect(dialog().open).toBe(false);

    document.querySelector<HTMLButtonElement>('[data-zylora-lead-open]')!.click();
    expect(dialog().open).toBe(true);
  });

  it('defers rather than stacking on another modal', () => {
    const other = document.createElement('dialog');
    other.setAttribute('open', '');
    other.setAttribute('aria-modal', 'true');
    document.body.append(other);
    runRuntime();

    vi.advanceTimersByTime(10_000);
    expect(dialog().open).toBe(false);

    other.remove();
    vi.advanceTimersByTime(500);
    expect(dialog().open).toBe(true);
  });

  it('Escape dismissal closes, restores focus, and prevents another automatic opening', () => {
    const opener = document.querySelector<HTMLButtonElement>('[data-zylora-lead-open]')!;
    opener.focus();
    runRuntime();
    vi.advanceTimersByTime(10_000);

    dialog().dispatchEvent(new Event('cancel', { cancelable: true }));
    expect(dialog().open).toBe(false);
    expect(document.activeElement).toBe(opener);
    expect(sessionStorage.getItem('zylora.lead-form.dismissed')).toBe('true');
  });

  it('marks successful form submission and never automatically reopens in the session', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            id: '0198dc65-affe-7000-8000-000000000001',
            source: 'FORM',
            duplicate: false,
            whatsapp_notification_queued: true,
          }),
          { status: 201, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    );
    runRuntime();
    vi.advanceTimersByTime(10_000);

    const form = document.querySelector<HTMLFormElement>('[data-zylora-lead-form]')!;
    form.querySelector<HTMLInputElement>('input[name="name"]')!.value = 'Ada';
    form.querySelector<HTMLTextAreaElement>('textarea[name="enquiry"]')!.value = 'Please call';
    form.querySelector<HTMLInputElement>('input[name="contact_consent"]')!.checked = true;
    form.dispatchEvent(new SubmitEvent('submit', { bubbles: true, cancelable: true }));
    await vi.waitFor(() =>
      expect(sessionStorage.getItem('zylora.lead-form.submitted')).toBe('true'),
    );

    expect(form.hidden).toBe(true);
    expect(document.querySelector<HTMLElement>('[data-zylora-lead-success]')!.hidden).toBe(false);
    document.querySelectorAll<HTMLButtonElement>('[data-zylora-lead-close]')[0]!.click();
    vi.advanceTimersByTime(60_000);
    expect(dialog().open).toBe(false);
    expect(fetch).toHaveBeenCalledTimes(2);
    const leadCall = vi.mocked(fetch).mock.calls.find(([url]) => String(url).endsWith('/leads'));
    expect(leadCall).toBeDefined();
    expect(String(leadCall?.[1]?.body)).not.toContain('chatbot');
    const analyticsCall = vi
      .mocked(fetch)
      .mock.calls.find(([url]) => String(url).endsWith('/analytics/events'));
    expect(String(analyticsCall?.[1]?.body)).not.toContain('Please call');
  });
});
