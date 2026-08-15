import { createServer } from 'node:http';
import { performance } from 'node:perf_hooks';

import { loadConfig, runtimeReadiness, staticReadiness } from './config.mjs';
import { PipelineFailure } from './errors/failure.mjs';
import { createPipelineDependencies, runBuildPipeline } from './orchestrator/pipeline.mjs';
import { bearerAuthorized } from './security/service-auth.mjs';

const config = loadConfig();
const dependencies = createPipelineDependencies(config);

function json(response, status, body) {
  const payload = JSON.stringify(body);
  response.writeHead(status, {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(payload),
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
  });
  response.end(payload);
}

function authorized(request) {
  return bearerAuthorized(request.headers.authorization, config.serviceToken);
}

async function readJson(request) {
  const chunks = [];
  let length = 0;
  const maxBytes = config.maxPromptBytes + 8192;
  for await (const chunk of request) {
    length += chunk.length;
    if (length > maxBytes) throw new PipelineFailure('REQUEST_TOO_LARGE', { httpStatus: 413 });
    chunks.push(chunk);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } catch {
    throw new PipelineFailure('INVALID_BUILD_REQUEST', { httpStatus: 400 });
  }
}

function validUuid(value) {
  return (
    typeof value === 'string' &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
  );
}

function validateRequest(payload, pathGenerationId, idempotencyKey) {
  if (
    !validUuid(pathGenerationId) ||
    payload.generation_id !== pathGenerationId ||
    !validUuid(payload.project_id) ||
    !validUuid(payload.owner_user_id) ||
    !validUuid(payload.lease_token) ||
    typeof payload.prompt !== 'string' ||
    payload.prompt.trim().length < 20 ||
    payload.prompt.trim().length > 2000 ||
    Buffer.byteLength(payload.prompt.trim(), 'utf8') > config.maxPromptBytes ||
    idempotencyKey !== `ai-generation:${pathGenerationId}`
  ) {
    throw new PipelineFailure('INVALID_BUILD_REQUEST', { retryable: false, httpStatus: 422 });
  }
}

function log(event, fields = {}) {
  process.stdout.write(
    `${JSON.stringify({ timestamp: new Date().toISOString(), event, service: 'zylora-ai-builder', ...fields })}\n`,
  );
}

const server = createServer(async (request, response) => {
  if (request.method === 'GET' && request.url === '/liveness') {
    return json(response, 200, { service: 'zylora-ai-builder', status: 'alive' });
  }
  if (request.method === 'GET' && ['/health', '/readiness'].includes(request.url)) {
    if (!authorized(request)) return json(response, 401, { error: 'UNAUTHORIZED' });
    const readiness = await runtimeReadiness(config);
    return json(response, readiness.ready ? 200 : 503, {
      service: 'zylora-ai-builder',
      status: readiness.ready ? 'ready' : 'not_ready',
      checks: readiness.checks,
      missing: readiness.missing,
    });
  }

  const match = request.url?.match(/^\/v1\/generations\/([0-9a-f-]+)\/execute$/i);
  if (request.method !== 'POST' || !match) return json(response, 404, { error: 'NOT_FOUND' });
  if (!authorized(request)) return json(response, 401, { error: 'UNAUTHORIZED', retryable: false });

  const configured = staticReadiness(config);
  if (!configured.ready) {
    return json(response, 503, { error: 'AI_BUILDER_CONFIGURATION_INVALID', retryable: false });
  }

  const generationId = match[1];
  const started = performance.now();
  try {
    const payload = await readJson(request);
    validateRequest(payload, generationId, request.headers['idempotency-key']);
    log('ai_generation_execution_started', {
      generation_id: generationId,
      project_id: payload.project_id,
    });
    const result = await runBuildPipeline(
      {
        generationId,
        projectId: payload.project_id,
        ownerUserId: payload.owner_user_id,
        prompt: payload.prompt.trim(),
      },
      dependencies,
    );
    log('ai_generation_execution_completed', {
      generation_id: generationId,
      project_id: payload.project_id,
      duration_ms: Math.round(performance.now() - started),
      artifact_bytes: result.artifact.size_bytes,
      provider: result.provider_name,
      model: result.provider_model,
    });
    return json(response, 200, result);
  } catch (error) {
    const known = error instanceof PipelineFailure;
    const code = known ? error.code : 'INTERNAL_GENERATION_ERROR';
    const retryable = known ? error.retryable : true;
    const httpStatus = known ? error.httpStatus : 500;
    log('ai_generation_execution_failed', {
      generation_id: generationId,
      duration_ms: Math.round(performance.now() - started),
      safe_error_code: code,
      retryable,
    });
    return json(response, httpStatus, { error: code, retryable });
  }
});

server.listen(config.port, '0.0.0.0', () => {
  log('service_started', { port: config.port, readiness: staticReadiness(config).ready });
});
