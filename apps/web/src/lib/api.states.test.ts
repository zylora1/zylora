import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiRequest, csrfToken } from './api';

describe('API client response states', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    document.cookie = 'zylora_user_csrf=; Max-Age=0; path=/';
  });

  it('handles no-content commands without parsing a body', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 204 }));
    await expect(apiRequest('/api/v1/auth/logout', { method: 'POST' })).resolves.toBeUndefined();
  });

  it('uses a generic safe error when the problem body is unavailable', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('not-json', { status: 500, headers: { 'Content-Type': 'text/plain' } }),
    );
    await expect(apiRequest('/api/v1/auth/login')).rejects.toThrow(
      'We could not complete that request. Try again.',
    );
  });

  it('reads only the named CSRF cookie and returns undefined when absent', () => {
    document.cookie = 'unrelated=value; path=/';
    document.cookie = 'zylora_user_csrf=csrf-value; path=/';

    expect(csrfToken('zylora_user_csrf')).toBe('csrf-value');
    expect(csrfToken('zylora_admin_csrf')).toBeUndefined();
  });
});
