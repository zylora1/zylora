function integer(name, fallback, minimum, maximum) {
  const value = Number.parseInt(process.env[name] ?? String(fallback), 10);
  if (!Number.isInteger(value) || value < minimum || value > maximum) {
    throw new Error(`${name}_invalid`);
  }
  return value;
}

function url(name) {
  const value = process.env[name] ?? '';
  if (!value) return '';
  const parsed = new URL(value);
  if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error(`${name}_invalid`);
  if (
    ['staging', 'production'].includes(process.env.AI_BUILDER_ENVIRONMENT) &&
    parsed.protocol !== 'https:'
  ) {
    throw new Error(`${name}_must_use_https`);
  }
  return value.replace(/\/$/, '');
}

export function loadConfig() {
  const environment = process.env.AI_BUILDER_ENVIRONMENT ?? 'development';
  if (!['development', 'test', 'staging', 'production'].includes(environment)) {
    throw new Error('AI_BUILDER_ENVIRONMENT_invalid');
  }
  const config = {
    environment,
    port: integer('PORT', 8090, 1, 65535),
    serviceToken: process.env.AI_BUILDER_SERVICE_TOKEN ?? '',
    providerUrl: url('AI_BUILDER_PROVIDER_URL'),
    providerToken: process.env.AI_BUILDER_PROVIDER_TOKEN ?? '',
    providerName: process.env.AI_BUILDER_PROVIDER_NAME ?? 'configured-http-provider',
    providerModel: process.env.AI_BUILDER_PROVIDER_MODEL ?? '',
    providerTimeoutMs: integer('AI_PROVIDER_TIMEOUT_SECONDS', 120, 10, 600) * 1000,
    providerRetries: integer('AI_PROVIDER_HTTP_RETRIES', 2, 0, 4),
    maxOutputTokens: integer('MAX_AI_OUTPUT_TOKENS', 32000, 1000, 128000),
    maxPromptBytes: integer('MAX_AI_PROMPT_BYTES', 8192, 1024, 65536),
    maxProviderResponseBytes: integer('MAX_AI_PROVIDER_RESPONSE_BYTES', 3500000, 100000, 10000000),
    sandboxUrl: url('AI_BUILDER_SANDBOX_URL'),
    sandboxToken: process.env.AI_BUILDER_SANDBOX_TOKEN ?? '',
    sandboxTimeoutMs: integer('AI_SANDBOX_TIMEOUT_SECONDS', 240, 30, 600) * 1000,
    maxArtifactBytes: integer('MAX_AI_ARTIFACT_BYTES', 52428800, 1048576, 262144000),
  };
  if (['staging', 'production'].includes(environment)) {
    if (config.serviceToken.length < 32) throw new Error('AI_BUILDER_SERVICE_TOKEN_invalid');
    if (config.providerToken.length < 32) throw new Error('AI_BUILDER_PROVIDER_TOKEN_invalid');
    if (config.sandboxToken.length < 32) throw new Error('AI_BUILDER_SANDBOX_TOKEN_invalid');
    if (new Set([config.serviceToken, config.providerToken, config.sandboxToken]).size !== 3) {
      throw new Error('AI_BUILDER_SERVICE_TOKENS_must_be_distinct');
    }
    if (!config.providerName || config.providerName === 'configured-http-provider') {
      throw new Error('AI_BUILDER_PROVIDER_NAME_invalid');
    }
  }
  return Object.freeze(config);
}

export function staticReadiness(config) {
  const missing = [];
  if (config.serviceToken.length < 32) missing.push('service_token');
  if (!config.providerUrl) missing.push('provider_url');
  if (config.providerToken.length < 32) missing.push('provider_token');
  if (!config.providerModel) missing.push('provider_model');
  if (!config.sandboxUrl) missing.push('sandbox_url');
  if (config.sandboxToken.length < 32) missing.push('sandbox_token');
  return { ready: missing.length === 0, missing };
}

async function dependencyReady(baseUrl, token) {
  try {
    const response = await fetch(`${baseUrl}/readiness`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(2000),
    });
    return response.ok;
  } catch {
    return false;
  }
}

export async function runtimeReadiness(config) {
  const staticResult = staticReadiness(config);
  if (!staticResult.ready) return { ...staticResult, checks: {} };
  const [provider, sandbox] = await Promise.all([
    dependencyReady(config.providerUrl, config.providerToken),
    dependencyReady(config.sandboxUrl, config.sandboxToken),
  ]);
  return {
    ready: provider && sandbox,
    missing: [],
    checks: {
      provider: provider ? 'ready' : 'not_ready',
      sandbox: sandbox ? 'ready' : 'not_ready',
    },
  };
}
