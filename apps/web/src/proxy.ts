import type { NextRequest } from 'next/server';
import { NextResponse } from 'next/server';

const adminHost = process.env.ADMIN_HOST ?? 'admin.localhost';

export function proxy(request: NextRequest) {
  const host = request.headers.get('host')?.split(':', 1)[0]?.toLowerCase();
  const path = request.nextUrl.pathname;
  const onAdminHost = host === adminHost;

  if (onAdminHost) {
    if (path.startsWith('/api/v1/admin')) return NextResponse.next();
    if (path === '/') return NextResponse.rewrite(new URL('/admin', request.url));
    if (path === '/login') return NextResponse.rewrite(new URL('/admin/login', request.url));
    if (!path.startsWith('/admin') && path !== '/health') {
      return NextResponse.rewrite(new URL('/admin/login', request.url));
    }
    return NextResponse.next();
  }

  if (path.startsWith('/admin') || path.startsWith('/api/v1/admin')) {
    return new NextResponse(null, { status: 404 });
  }
  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|robots.txt|sitemap.xml).*)'],
};
