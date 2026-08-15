import { failure } from '../errors/failure.mjs';

const RETRYABLE_STATUS = new Set([408, 425, 429, 500, 502, 503, 504]);

/** @typedef {{files: Record<string,string>, providerName: string, providerModel: string}} GeneratedSite */

/**
 * Provider-neutral contract. Implementations return plain generated files and safe metadata only.
 * @interface
 */
export class AIWebsiteProvider {
  async generate(_request) {
    throw new Error('AIWebsiteProvider.generate must be implemented');
  }
}

export class HttpAIWebsiteProvider extends AIWebsiteProvider {
  constructor(config, { fetchImpl = fetch, sleep = defaultSleep, random = Math.random } = {}) {
    super();
    this.config = config;
    this.fetchImpl = fetchImpl;
    this.sleep = sleep;
    this.random = random;
  }

  async generate({ generationId, prompt }) {
    let lastFailure;
    for (let attempt = 0; attempt <= this.config.providerRetries; attempt += 1) {
      try {
        return await this.#attempt({ generationId, prompt });
      } catch (error) {
        lastFailure = error;
        if (!error.retryable || attempt >= this.config.providerRetries) throw error;
        const base = Math.min(4000, 250 * 2 ** attempt);
        await this.sleep(base + Math.floor(this.random() * Math.max(1, base / 3)));
      }
    }
    throw lastFailure;
  }

  async #attempt({ generationId, prompt }) {
    let response;
    try {
      response = await this.fetchImpl(`${this.config.providerUrl}/v1/generate-next-site`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${this.config.providerToken}`,
          'Content-Type': 'application/json',
          'Idempotency-Key': `ai-generation:${generationId}`,
        },
        body: JSON.stringify({
          generation_id: generationId,
          prompt,
          target: 'business-website',
          framework: 'nextjs-app-router',
          max_output_tokens: this.config.maxOutputTokens,
          constraints: {
            typescript: true,
            package_profile: 'zylora-next-v1',
            arbitrary_dependencies: false,
            arbitrary_scripts: false,
          },
        }),
        signal: AbortSignal.timeout(this.config.providerTimeoutMs),
      });
    } catch (error) {
      if (error?.name === 'TimeoutError') {
        throw failure('PROVIDER_TIMEOUT', { retryable: true, httpStatus: 504 });
      }
      throw failure('PROVIDER_UNAVAILABLE', { retryable: true, httpStatus: 503 });
    }
    if (!response.ok) throw classifyStatus(response.status);
    const text = await response.text();
    if (Buffer.byteLength(text) > this.config.maxProviderResponseBytes) {
      throw failure('INVALID_PROVIDER_RESPONSE', { retryable: false, httpStatus: 502 });
    }
    let payload;
    try {
      payload = JSON.parse(text);
    } catch {
      throw failure('INVALID_PROVIDER_RESPONSE', { retryable: false, httpStatus: 502 });
    }
    if (!payload || typeof payload.files !== 'object' || Array.isArray(payload.files)) {
      throw failure('INVALID_PROVIDER_RESPONSE', { retryable: false, httpStatus: 502 });
    }
    return {
      files: payload.files,
      providerName: this.config.providerName,
      providerModel: this.config.providerModel,
    };
  }
}

function classifyStatus(status) {
  if (status === 429) {
    return failure('PROVIDER_RATE_LIMITED', { retryable: true, httpStatus: 503 });
  }
  if (RETRYABLE_STATUS.has(status)) {
    return failure('PROVIDER_UNAVAILABLE', { retryable: true, httpStatus: 503 });
  }
  if (status === 401 || status === 403) {
    return failure('PROVIDER_AUTHENTICATION_FAILED', { retryable: false, httpStatus: 503 });
  }
  if (status === 422) {
    return failure('GENERATION_POLICY_REJECTED', { retryable: false, httpStatus: 422 });
  }
  return failure('PROVIDER_REQUEST_REJECTED', { retryable: false, httpStatus: 422 });
}

function defaultSleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}
