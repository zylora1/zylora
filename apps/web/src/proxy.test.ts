import { NextRequest } from 'next/server';
import { describe, expect, it } from 'vitest';

import { proxy } from './proxy';

describe('Super Admin host isolation', () => {
  it('rewrites the isolated admin host root to its own application', () => {
    const response = proxy(
      new NextRequest('http://admin.localhost/', { headers: { host: 'admin.localhost' } }),
    );

    expect(response.headers.get('x-middleware-rewrite')).toBe('http://admin.localhost/admin');
    expect(response.headers.get('x-robots-tag')).toBe('noindex, nofollow');
    expect(response.headers.get('cache-control')).toBe('private, no-store');
  });

  it('does not expose admin routes on the User host', () => {
    const response = proxy(
      new NextRequest('http://localhost/admin/login', { headers: { host: 'localhost' } }),
    );

    expect(response.status).toBe(404);
  });
});
