import { NextRequest } from 'next/server';
import { describe, expect, it } from 'vitest';

import { proxy } from './proxy';

function request(path: string, host = 'admin.localhost') {
  return new NextRequest(`http://${host}${path}`, { headers: { host } });
}

describe('proxy route states', () => {
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

  it('allows only existing admin and operational health paths on the admin host', () => {
    expect(proxy(request('/admin/login')).headers.get('x-middleware-next')).toBe('1');
    expect(proxy(request('/health')).headers.get('x-middleware-next')).toBe('1');
    expect(proxy(request('/api/v1/admin/me')).headers.get('x-middleware-next')).toBe('1');
  });

  it('passes ordinary User routes but rejects Admin APIs on the User host', () => {
    expect(proxy(request('/login', 'localhost')).headers.get('x-middleware-next')).toBe('1');
    expect(proxy(request('/api/v1/admin/me', 'localhost')).status).toBe(404);
  });
});
