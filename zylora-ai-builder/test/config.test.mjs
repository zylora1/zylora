import assert from 'node:assert/strict';
import test, { afterEach, beforeEach } from 'node:test';

import { loadConfig } from '../src/config.mjs';

const KEYS = [
  'AI_BUILDER_ENVIRONMENT',
  'AI_BUILDER_SERVICE_TOKEN',
  'AI_BUILDER_PROVIDER_URL',
  'AI_BUILDER_PROVIDER_TOKEN',
  'AI_BUILDER_PROVIDER_NAME',
  'AI_BUILDER_PROVIDER_MODEL',
  'AI_BUILDER_SANDBOX_URL',
  'AI_BUILDER_SANDBOX_TOKEN',
];

let original;

beforeEach(() => {
  original = Object.fromEntries(KEYS.map((key) => [key, process.env[key]]));
  Object.assign(process.env, {
    AI_BUILDER_ENVIRONMENT: 'production',
    AI_BUILDER_SERVICE_TOKEN: 'core-builder-token-0000000000000001',
    AI_BUILDER_PROVIDER_URL: 'https://provider.internal.example',
    AI_BUILDER_PROVIDER_TOKEN: 'builder-provider-token-000000000001',
    AI_BUILDER_PROVIDER_NAME: 'approved-provider',
    AI_BUILDER_PROVIDER_MODEL: 'approved-model',
    AI_BUILDER_SANDBOX_URL: 'https://sandbox.internal.example',
    AI_BUILDER_SANDBOX_TOKEN: 'builder-sandbox-token-000000000001',
  });
});

afterEach(() => {
  for (const [key, value] of Object.entries(original)) {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
});

test('production configuration requires explicit distinct service credentials', () => {
  const config = loadConfig();
  assert.equal(config.environment, 'production');
  assert.equal(config.providerName, 'approved-provider');

  process.env.AI_BUILDER_SANDBOX_TOKEN = process.env.AI_BUILDER_PROVIDER_TOKEN;
  assert.throws(() => loadConfig(), /SERVICE_TOKENS_must_be_distinct/);
});

test('production configuration rejects short secrets and implicit provider identity', () => {
  process.env.AI_BUILDER_PROVIDER_TOKEN = 'too-short';
  assert.throws(() => loadConfig(), /PROVIDER_TOKEN_invalid/);

  process.env.AI_BUILDER_PROVIDER_TOKEN = 'builder-provider-token-000000000001';
  process.env.AI_BUILDER_PROVIDER_NAME = 'configured-http-provider';
  assert.throws(() => loadConfig(), /PROVIDER_NAME_invalid/);
});

test('builder environment must be one of the explicit deployment stages', () => {
  process.env.AI_BUILDER_ENVIRONMENT = 'prod';
  assert.throws(() => loadConfig(), /AI_BUILDER_ENVIRONMENT_invalid/);
});
test('staging uses the same transport and credential boundary as production', () => {
  process.env.AI_BUILDER_ENVIRONMENT = 'staging';
  assert.equal(loadConfig().environment, 'staging');
  process.env.AI_BUILDER_PROVIDER_URL = 'http://provider.internal.example';
  assert.throws(() => loadConfig(), /PROVIDER_URL_must_use_https/);
});
