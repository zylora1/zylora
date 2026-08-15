import test from 'node:test';
import assert from 'node:assert/strict';

import { HttpAIWebsiteProvider } from '../src/provider/http-provider.mjs';
import { SandboxExecutor } from '../src/sandbox/client.mjs';

const generationId = '11111111-1111-4111-8111-111111111111';
const projectId = '22222222-2222-4222-8222-222222222222';
const ownerUserId = '33333333-3333-4333-8333-333333333333';
const config = {
  providerUrl: 'https://provider.test',
  providerToken: 'provider-token',
  providerName: 'test-provider',
  providerModel: 'test-model',
  providerTimeoutMs: 1000,
  providerRetries: 2,
  maxOutputTokens: 32000,
  maxProviderResponseBytes: 3500000,
  sandboxUrl: 'https://sandbox.test',
  sandboxToken: 'sandbox-token',
  sandboxTimeoutMs: 1000,
  maxArtifactBytes: 52428800,
};

const files = {
  'app/layout.tsx': 'export default function Layout({children}) { return children }',
  'app/page.tsx': 'export default function Page() { return <main /> }',
};

test('provider retries 429 with one stable idempotency key and no prompt logging surface', async () => {
  const requests = [];
  const fetchImpl = async (_url, init) => {
    requests.push(init);
    return requests.length === 1
      ? new Response('{}', { status: 429 })
      : new Response(JSON.stringify({ files }), { status: 200 });
  };
  const provider = new HttpAIWebsiteProvider(config, {
    fetchImpl,
    sleep: async () => {},
    random: () => 0,
  });
  const result = await provider.generate({
    generationId,
    prompt: 'Build a safe business website.',
  });
  assert.equal(requests.length, 2);
  assert.equal(requests[0].headers['Idempotency-Key'], `ai-generation:${generationId}`);
  assert.equal(requests[1].headers['Idempotency-Key'], `ai-generation:${generationId}`);
  assert.deepEqual(result.files, files);
});

test('provider does not retry authentication or policy rejection', async () => {
  for (const status of [401, 403, 422]) {
    let calls = 0;
    const provider = new HttpAIWebsiteProvider(config, {
      fetchImpl: async () => {
        calls += 1;
        return new Response('{}', { status });
      },
      sleep: async () => {},
    });
    await assert.rejects(
      provider.generate({ generationId, prompt: 'Build a safe business website.' }),
      (error) => error.retryable === false,
    );
    assert.equal(calls, 1);
  }
});

test('sandbox request contains fixed isolation policy and accepts only owner-scoped artifacts', async () => {
  let body;
  const digest = 'a'.repeat(64);
  const sandbox = new SandboxExecutor(config, {
    fetchImpl: async (_url, init) => {
      body = JSON.parse(init.body);
      return new Response(
        JSON.stringify({
          status: 'COMPLETED',
          generation_id: generationId,
          artifact: {
            object_key: `ai-sites/${ownerUserId}/${projectId}/${generationId}/${digest}.tar.gz`,
            checksum_sha256: digest,
            size_bytes: 1024,
            content_type: 'application/gzip',
          },
        }),
        { status: 200 },
      );
    },
  });
  await sandbox.validateAndBuild({ generationId, projectId, ownerUserId, files });
  assert.equal(body.limits.network, 'none');
  assert.equal(body.limits.read_only_root, true);
  assert.equal(body.limits.capability_drop, 'all');
  assert.equal(body.lifecycle_scripts, false);
  assert.deepEqual(body.environment_allowlist, []);
  assert.equal(body.dependency_profile, 'zylora-next-v1-pinned-lockfile');
});

test('sandbox rejects forged cross-owner artifact keys and terminal build errors', async () => {
  const digest = 'b'.repeat(64);
  const forged = new SandboxExecutor(config, {
    fetchImpl: async () =>
      new Response(
        JSON.stringify({
          status: 'COMPLETED',
          generation_id: generationId,
          artifact: {
            object_key: `ai-sites/forged/${projectId}/${generationId}/${digest}.tar.gz`,
            checksum_sha256: digest,
            size_bytes: 1024,
            content_type: 'application/gzip',
          },
        }),
        { status: 200 },
      ),
  });
  await assert.rejects(
    forged.validateAndBuild({ generationId, projectId, ownerUserId, files }),
    /SANDBOX_RESULT_INVALID/,
  );
  const failed = new SandboxExecutor(config, {
    fetchImpl: async () => new Response('{}', { status: 422 }),
  });
  await assert.rejects(
    failed.validateAndBuild({ generationId, projectId, ownerUserId, files }),
    (error) => error.code === 'SANDBOX_BUILD_FAILED' && error.retryable === false,
  );
});
test('provider retry exhaustion is bounded and response failures are terminal', async () => {
  let calls = 0;
  const delays = [];
  const unavailable = new HttpAIWebsiteProvider(config, {
    fetchImpl: async () => {
      calls += 1;
      return new Response('{}', { status: 503 });
    },
    sleep: async (delay) => delays.push(delay),
    random: () => 0,
  });
  await assert.rejects(
    unavailable.generate({ generationId, prompt: 'Build a safe business website.' }),
    (error) => error.code === 'PROVIDER_UNAVAILABLE' && error.retryable === true,
  );
  assert.equal(calls, config.providerRetries + 1);
  assert.deepEqual(delays, [250, 500]);

  for (const response of [
    new Response('not-json', { status: 200 }),
    new Response(JSON.stringify({ unexpected: true }), { status: 200 }),
    new Response('x'.repeat(config.maxProviderResponseBytes + 1), { status: 200 }),
  ]) {
    const provider = new HttpAIWebsiteProvider(
      { ...config, providerRetries: 0 },
      { fetchImpl: async () => response },
    );
    await assert.rejects(
      provider.generate({ generationId, prompt: 'Build a safe business website.' }),
      (error) => error.code === 'INVALID_PROVIDER_RESPONSE' && error.retryable === false,
    );
  }
});

test('provider and sandbox transport failures use stable retryable classifications', async () => {
  for (const name of ['TimeoutError', 'NetworkError']) {
    const provider = new HttpAIWebsiteProvider(
      { ...config, providerRetries: 0 },
      {
        fetchImpl: async () => {
          const error = new Error('sensitive transport detail');
          error.name = name;
          throw error;
        },
      },
    );
    await assert.rejects(
      provider.generate({ generationId, prompt: 'Build a safe business website.' }),
      (error) =>
        error.code === (name === 'TimeoutError' ? 'PROVIDER_TIMEOUT' : 'PROVIDER_UNAVAILABLE') &&
        error.retryable === true &&
        !error.message.includes('sensitive transport detail'),
    );
  }

  const timedOut = new SandboxExecutor(config, {
    fetchImpl: async () => {
      const error = new Error('sandbox host detail');
      error.name = 'TimeoutError';
      throw error;
    },
  });
  await assert.rejects(
    timedOut.validateAndBuild({ generationId, projectId, ownerUserId, files }),
    (error) => error.code === 'SANDBOX_TIMEOUT' && error.retryable === true,
  );

  const unavailable = new SandboxExecutor(config, {
    fetchImpl: async () => new Response('{}', { status: 503 }),
  });
  await assert.rejects(
    unavailable.validateAndBuild({ generationId, projectId, ownerUserId, files }),
    (error) => error.code === 'SANDBOX_UNAVAILABLE' && error.retryable === true,
  );
});
