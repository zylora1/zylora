import { performance } from 'node:perf_hooks';

import { HttpAIWebsiteProvider } from '../provider/http-provider.mjs';
import { SandboxExecutor } from '../sandbox/client.mjs';
import { validateGeneratedFiles } from '../security/validate-files.mjs';

export async function runBuildPipeline(
  { generationId, projectId, ownerUserId, prompt },
  { provider, sandbox, config },
) {
  const durations = {};
  let started = performance.now();
  const generated = await provider.generate({ generationId, prompt });
  durations.generating = elapsed(started);

  started = performance.now();
  const files = validateGeneratedFiles(generated.files);
  durations.validating = elapsed(started);
  durations.scanning = 0;

  started = performance.now();
  const artifact = await sandbox.validateAndBuild({
    generationId,
    projectId,
    ownerUserId,
    files,
  });
  durations.sandboxing = elapsed(started);
  durations.building = 0;
  durations.storing = 0;
  return {
    generation_id: generationId,
    status: 'COMPLETED',
    artifact,
    provider_name: generated.providerName,
    provider_model: generated.providerModel,
    stage_durations_ms: durations,
  };
}

export function createPipelineDependencies(config, overrides = {}) {
  return {
    config,
    provider: overrides.provider ?? new HttpAIWebsiteProvider(config),
    sandbox: overrides.sandbox ?? new SandboxExecutor(config),
  };
}

function elapsed(started) {
  return Math.max(0, Math.round(performance.now() - started));
}
