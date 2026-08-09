import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiRequest } from './api';

describe('apiRequest', () => {
  afterEach(() => vi.restoreAllMocks());

  it('always uses browser credentials and JSON for commands', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ status: 'accepted' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await apiRequest('/api/v1/auth/signup', { method: 'POST', body: '{}' });

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/auth/signup',
      expect.objectContaining({
        credentials: 'include',
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
      }),
    );
  });

  it('surfaces only the safe problem detail', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Email or password is incorrect.' }), {
        status: 401,
      }),
    );

    await expect(apiRequest('/api/v1/auth/login')).rejects.toThrow(
      'Email or password is incorrect.',
    );
  });
});
