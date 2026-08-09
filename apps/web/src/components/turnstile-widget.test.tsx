import { render, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TurnstileWidget } from './turnstile-widget';

vi.mock('next/script', async () => {
  const React = await import('react');
  function ScriptMock({ onLoad }: { onLoad: () => void }) {
    React.useEffect(onLoad, [onLoad]);
    return null;
  }
  return { default: ScriptMock };
});

describe('TurnstileWidget', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    delete window.turnstile;
  });

  it('renders an interaction-only challenge and returns a short-lived token', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ enabled: true, site_key: 'public-site-key' })),
    );
    let options: Record<string, unknown> = {};
    window.turnstile = {
      render: vi.fn((_container, next) => {
        options = next;
        return 'widget-id';
      }),
      remove: vi.fn(),
    };
    const onToken = vi.fn();
    const onRequirementChange = vi.fn();
    const onError = vi.fn();

    render(
      <TurnstileWidget
        action="signup"
        resetKey={0}
        onToken={onToken}
        onRequirementChange={onRequirementChange}
        onError={onError}
      />,
    );

    await waitFor(() => expect(window.turnstile?.render).toHaveBeenCalledOnce());
    expect(options).toMatchObject({
      sitekey: 'public-site-key',
      action: 'signup',
      appearance: 'interaction-only',
      execution: 'render',
    });
    (options.callback as (token: string) => void)('single-use-token');
    expect(onToken).toHaveBeenLastCalledWith('single-use-token');
    (options['expired-callback'] as () => void)();
    expect(onToken).toHaveBeenLastCalledWith(null);
    (options['timeout-callback'] as () => void)();
    expect((options['error-callback'] as () => boolean)()).toBe(true);
    expect(onError).toHaveBeenCalledWith('Security verification failed. Please try again.');
    expect(onRequirementChange).toHaveBeenCalledWith(true);
  });

  it('does not load Cloudflare or require a token when disabled', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ enabled: false, site_key: null })),
    );
    const onToken = vi.fn();
    const onRequirementChange = vi.fn();

    render(
      <TurnstileWidget
        action="login"
        resetKey={0}
        onToken={onToken}
        onRequirementChange={onRequirementChange}
        onError={vi.fn()}
      />,
    );

    await waitFor(() => expect(onRequirementChange).toHaveBeenCalledWith(false));
    expect(onToken).toHaveBeenCalledWith(null);
    expect(window.turnstile).toBeUndefined();
  });

  it('fails closed when runtime configuration cannot be loaded', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('offline'));
    const onRequirementChange = vi.fn();
    const onError = vi.fn();

    render(
      <TurnstileWidget
        action="admin_login"
        resetKey={0}
        onToken={vi.fn()}
        onRequirementChange={onRequirementChange}
        onError={onError}
      />,
    );

    await waitFor(() => expect(onRequirementChange).toHaveBeenCalledWith(true));
    expect(onError).toHaveBeenCalledWith('Security verification is unavailable.');
  });
});
