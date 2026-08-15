import { NextRequest } from 'next/server';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { proxy } from './proxy';

function request(path: string, host = 'admin.localhost') {
  return new NextRequest(`http://${host}${path}`, { headers: { host } });
}

describe('proxy route states', () => {
  afterEach(() => vi.unstubAllEnvs());
  it('maps the friendly admin login path to its isolated route', () => {
    expect(proxy(request('/login')).headers.get('x-middleware-rewrite')).toBe(
      'http://admin.localhost/admin/login',
    );
  });

  it('keeps arbitrary User routes out of the admin host', () => {
    expect(proxy(request('/signup')).headers.get('x-middleware-rewrite')).toBe(
      'http://admin.localhost/admin/login',
    );
  });

  it('allows only Admin APIs, shared challenge configuration, and operational health paths on the admin host', () => {
    expect(proxy(request('/admin/login')).headers.get('x-middleware-next')).toBe('1');
    expect(proxy(request('/health')).headers.get('x-middleware-next')).toBe('1');
    expect(proxy(request('/api/v1/admin/me')).headers.get('x-middleware-next')).toBe('1');
    expect(proxy(request('/api/v1/auth/challenge/config')).headers.get('x-middleware-next')).toBe(
      '1',
    );
  });

  it('passes ordinary User routes but rejects Admin APIs on the User host', () => {
    expect(proxy(request('/login', 'localhost')).headers.get('x-middleware-next')).toBe('1');
    expect(proxy(request('/api/v1/admin/me', 'localhost')).status).toBe(404);
  });

  it('adds a fresh nonce CSP that permits Turnstile and React development debugging', () => {
    const response = proxy(request('/login', 'localhost'));
    const csp = response.headers.get('content-security-policy');

    expect(csp).toMatch(/script-src 'self' 'nonce-[A-Za-z0-9-]+' 'strict-dynamic'/);
    expect(csp).toContain('https://challenges.cloudflare.com');
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("'unsafe-eval'");
    expect(response.headers.get('x-nonce')).toBeNull();
  });

  it('keeps unsafe eval out of the production CSP', () => {
    vi.stubEnv('NODE_ENV', 'production');

    const response = proxy(request('/login', 'localhost'));
    const csp = response.headers.get('content-security-policy');

    expect(csp).not.toContain("'unsafe-eval'");
    expect(csp).toContain("'strict-dynamic'");
    expect(response.headers.get('strict-transport-security')).toBe(
      'max-age=63072000; includeSubDomains',
    );
  });
});
