import type { NextConfig } from 'next';

const securityHeaders = [
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'Cross-Origin-Opener-Policy', value: 'same-origin' },
  { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=(), payment=()' },
];

const privateHeaders = [
  { key: 'Cache-Control', value: 'private, no-store' },
  { key: 'X-Robots-Tag', value: 'noindex, nofollow, noarchive' },
];

const privateRoutes = [
  '/health',
  '/app/:path*',
  '/admin/:path*',
  '/login',
  '/signup',
  '/verify-email',
  '/forgot-password',
  '/reset-password',
  '/unsubscribe',
  '/dev/:path*',
  '/templates/:slug/preview',
] as const;

const nextConfig: NextConfig = {
  allowedDevOrigins: ['127.0.0.1'],
  poweredByHeader: false,
  reactStrictMode: true,
  async rewrites() {
    const apiOrigin = process.env.API_INTERNAL_URL ?? 'http://127.0.0.1:8000';
    return [{ source: '/api/v1/:path*', destination: `${apiOrigin}/api/v1/:path*` }];
  },
  async headers() {
    return [
      { source: '/(.*)', headers: securityHeaders },
      ...privateRoutes.map((source) => ({ source, headers: privateHeaders })),
    ];
  },
};

export default nextConfig;
