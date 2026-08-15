import type { NextRequest } from 'next/server';
import { NextResponse } from 'next/server';

const adminHost = process.env.ADMIN_HOST ?? 'admin.localhost';

function contentSecurityPolicy(nonce: string) {
  const developmentScriptPolicy = process.env.NODE_ENV === 'production' ? '' : " 'unsafe-eval'";

  return [
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic' https://challenges.cloudflare.com${developmentScriptPolicy}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob: https:",
    "font-src 'self' data:",
    "connect-src 'self' https://challenges.cloudflare.com",
    'frame-src https://challenges.cloudflare.com',
  ].join('; ');
}

function securedRequestHeaders(request: NextRequest, csp: string) {
  const headers = new Headers(request.headers);
  headers.set('Content-Security-Policy', csp);
  headers.set('x-nonce', csp.match(/'nonce-([^']+)'/)?.[1] ?? '');
  return headers;
}

function securityResponse(response: NextResponse, csp: string) {
  response.headers.set('Content-Security-Policy', csp);
  response.headers.set('X-Content-Type-Options', 'nosniff');
  response.headers.set('X-Frame-Options', 'DENY');
  response.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  response.headers.set(
    'Permissions-Policy',
    'camera=(), microphone=(), geolocation=(), payment=()',
  );
  if (process.env.NODE_ENV === 'production') {
    response.headers.set('Strict-Transport-Security', 'max-age=63072000; includeSubDomains');
  }
  return response;
}

function nextResponse(request: NextRequest, csp: string) {
  return securityResponse(
    NextResponse.next({ request: { headers: securedRequestHeaders(request, csp) } }),
    csp,
  );
}

function rewriteResponse(request: NextRequest, destination: URL, csp: string) {
  return securityResponse(
    NextResponse.rewrite(destination, {
      request: { headers: securedRequestHeaders(request, csp) },
    }),
    csp,
  );
}

function privateAdminResponse(response: NextResponse) {
  response.headers.set('Cache-Control', 'private, no-store');
  response.headers.set('X-Robots-Tag', 'noindex, nofollow');
  return response;
}

export function proxy(request: NextRequest) {
  const nonce = crypto.randomUUID();
  const csp = contentSecurityPolicy(nonce);
  const host = request.headers.get('host')?.split(':', 1)[0]?.toLowerCase();
  const path = request.nextUrl.pathname;
  const onAdminHost = host === adminHost;

  if (onAdminHost) {
    if (path.startsWith('/api/v1/admin') || path === '/api/v1/auth/challenge/config') {
      return privateAdminResponse(nextResponse(request, csp));
    }
    if (path === '/') {
      return privateAdminResponse(rewriteResponse(request, new URL('/admin', request.url), csp));
    }
    if (path === '/login') {
      return privateAdminResponse(
        rewriteResponse(request, new URL('/admin/login', request.url), csp),
      );
    }
    if (!path.startsWith('/admin') && path !== '/health') {
      return privateAdminResponse(
        rewriteResponse(request, new URL('/admin/login', request.url), csp),
      );
    }
    return privateAdminResponse(nextResponse(request, csp));
  }

  if (path.startsWith('/admin') || path.startsWith('/api/v1/admin')) {
    return securityResponse(new NextResponse(null, { status: 404 }), csp);
  }
  return nextResponse(request, csp);
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|robots.txt|sitemap.xml).*)'],
};
