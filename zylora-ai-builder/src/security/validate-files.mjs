import path from 'node:path';

import { failure } from '../errors/failure.mjs';

const MAX_FILES = 180;
const MAX_FILE_BYTES = 250_000;
const MAX_TOTAL_BYTES = 2_500_000;
const ALLOWED_EXTENSIONS = new Set([
  '.ts',
  '.tsx',
  '.js',
  '.mjs',
  '.css',
  '.json',
  '.svg',
  '.txt',
  '.md',
]);
const BLOCKED_PATHS =
  /(^|\/)(node_modules|\.git|\.next|\.env|secrets?|credentials?|\.aws|\.ssh)(\/|$)/i;
const BLOCKED_SOURCE = [
  /\b(?:node:)?child_process\b/i,
  /\b(?:node:)?(?:fs|net|tls|dns|cluster|worker_threads|vm)\b/i,
  /\b(?:exec|execFile|spawn|fork|eval)Sync\s*\(/i,
  /\b(?:exec|execFile|spawn|fork|eval)\s*\(/i,
  /\bnew\s+Function\b/i,
  /\bprocess\s*\./i,
  /\b(?:Deno|Bun)\s*\./i,
  /\b(?:preinstall|postinstall|prepare)\b/i,
  /(?:169\.254\.169\.254|metadata\.google\.internal|localhost|127\.0\.0\.1|0\.0\.0\.0)/i,
  /(?:\/etc\/|\/proc\/|\/sys\/|\.aws\/credentials|\.ssh\/)/i,
  /<script\b|<iframe\b|<object\b|<embed\b|<foreignObject\b|\bon[a-z]+\s*=/i,
  /(?:javascript|vbscript|data\s*:\s*text\/html)\s*:/i,
  /\b(?:fetch|XMLHttpRequest|WebSocket|EventSource)\s*\(/i,
  /\b(?:window\.)?location\s*(?:=|\.|\[)/i,
  /(?:src|href)\s*=\s*["']https?:\/\//i,
  /(?:@import\s+|url\s*\()["']?https?:\/\//i,
];

export function validateGeneratedFiles(files) {
  if (!files || typeof files !== 'object' || Array.isArray(files)) {
    throw unsafe('GENERATED_PROJECT_INVALID');
  }
  const entries = Object.entries(files);
  if (entries.length === 0 || entries.length > MAX_FILES) {
    throw unsafe('GENERATED_PROJECT_INVALID');
  }
  let total = 0;
  const normalized = Object.create(null);
  for (const [rawPath, content] of entries) {
    if (typeof rawPath !== 'string' || typeof content !== 'string') {
      throw unsafe('GENERATED_PROJECT_INVALID');
    }
    if (
      rawPath !== rawPath.normalize('NFC') ||
      /[\u0000-\u001f\u007f\uD800-\uDFFF%]/u.test(rawPath) ||
      /^[a-z]:/i.test(rawPath)
    ) {
      throw unsafe('GENERATED_PROJECT_UNSAFE');
    }
    const filePath = rawPath.replaceAll('\\', '/');
    const safePath = path.posix.normalize(filePath);
    if (
      safePath === '..' ||
      safePath.startsWith('../') ||
      safePath.startsWith('/') ||
      safePath !== filePath ||
      BLOCKED_PATHS.test(safePath)
    ) {
      throw unsafe('GENERATED_PROJECT_UNSAFE');
    }
    const extension = path.posix.extname(safePath);
    if (!ALLOWED_EXTENSIONS.has(extension)) throw unsafe('GENERATED_PROJECT_UNSAFE');
    if (safePath === 'package.json' || safePath.endsWith('/package.json')) {
      throw unsafe('GENERATED_PROJECT_UNSAFE');
    }
    const size = Buffer.byteLength(content, 'utf8');
    total += size;
    if (size > MAX_FILE_BYTES || total > MAX_TOTAL_BYTES || content.includes('\u0000')) {
      throw unsafe('GENERATED_PROJECT_INVALID');
    }
    if (BLOCKED_SOURCE.some((pattern) => pattern.test(content))) {
      throw unsafe('GENERATED_PROJECT_UNSAFE');
    }
    normalized[safePath] = content;
  }
  if (!normalized['app/layout.tsx'] || !normalized['app/page.tsx']) {
    throw unsafe('GENERATED_PROJECT_INVALID');
  }
  return normalized;
}

function unsafe(code) {
  return failure(code, { retryable: false, httpStatus: 422 });
}
