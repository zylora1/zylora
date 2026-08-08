import { NextResponse } from 'next/server';

export function GET() {
  return NextResponse.json(
    {
      service: 'zylora-web',
      status: 'alive',
      version: process.env.APP_VERSION ?? '0.1.0',
    },
    { headers: { 'Cache-Control': 'no-store' } },
  );
}
