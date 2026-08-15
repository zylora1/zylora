import { timingSafeEqual } from 'node:crypto';

export function bearerAuthorized(authorization, expectedToken) {
  const candidate = authorization?.replace(/^Bearer\s+/i, '') ?? '';
  if (!expectedToken || candidate.length !== expectedToken.length) return false;
  return timingSafeEqual(Buffer.from(candidate), Buffer.from(expectedToken));
}
