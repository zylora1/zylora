import { failure } from '../errors/failure.mjs';

const RETRYABLE_STATUS = new Set([408, 425, 429, 500, 502, 503, 504]);
const ALLOWED_CONTENT_TYPES = new Set(['application/gzip', 'application/x-tar', 'application/zip']);

export class SandboxExecutor {
  constructor(config, { fetchImpl = fetch } = {}) {
    this.config = config;
    this.fetchImpl = fetchImpl;
  }

  async validateAndBuild({ generationId, projectId, ownerUserId, files }) {
    let response;
    try {
      response = await this.fetchImpl(`${this.config.sandboxUrl}/v1/builds`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${this.config.sandboxToken}`,
          'Content-Type': 'application/json',
          'Idempotency-Key': `ai-generation:${generationId}`,
        },
        body: JSON.stringify({
          generation_id: generationId,
          project_id: projectId,
          owner_user_id: ownerUserId,
          runtime_profile: 'zylora-next-v1',
          dependency_profile: 'zylora-next-v1-pinned-lockfile',
          lifecycle_scripts: false,
          limits: {
            cpu: 1,
            memory_mb: 512,
            timeout_seconds: Math.floor(this.config.sandboxTimeoutMs / 1000),
            network: 'none',
            pids: 128,
            read_only_root: true,
            disposable_workspace: true,
            tmpfs_mb: 256,
            capability_drop: 'all',
            no_new_privileges: true,
          },
          environment_allowlist: [],
          files,
          checks: [
            'fixed-dependencies',
            'no-lifecycle-scripts',
            'typecheck',
            'build',
            'browser-smoke',
            'seo',
            'accessibility',
            'artifact-scan',
          ],
          artifact: {
            immutable: true,
            content_addressed: true,
            prefix: `ai-sites/${ownerUserId}/${projectId}/${generationId}/`,
            max_bytes: this.config.maxArtifactBytes,
          },
        }),
        signal: AbortSignal.timeout(this.config.sandboxTimeoutMs + 5000),
      });
    } catch (error) {
      if (error?.name === 'TimeoutError') {
        throw failure('SANDBOX_TIMEOUT', { retryable: true, httpStatus: 504 });
      }
      throw failure('SANDBOX_UNAVAILABLE', { retryable: true, httpStatus: 503 });
    }
    if (!response.ok) {
      if (RETRYABLE_STATUS.has(response.status)) {
        throw failure(response.status === 408 ? 'SANDBOX_TIMEOUT' : 'SANDBOX_UNAVAILABLE', {
          retryable: true,
          httpStatus: 503,
        });
      }
      throw failure('SANDBOX_BUILD_FAILED', { retryable: false, httpStatus: 422 });
    }
    let result;
    try {
      result = await response.json();
    } catch {
      throw failure('SANDBOX_RESULT_INVALID', { retryable: false, httpStatus: 502 });
    }
    const artifact = result?.artifact;
    const expectedPrefix = `ai-sites/${ownerUserId}/${projectId}/${generationId}/`;
    if (
      result?.status !== 'COMPLETED' ||
      result?.generation_id !== generationId ||
      !artifact ||
      typeof artifact.object_key !== 'string' ||
      !artifact.object_key.startsWith(expectedPrefix) ||
      !/^[a-f0-9]{64}$/.test(artifact.checksum_sha256 ?? '') ||
      !artifact.object_key.endsWith(`/${artifact.checksum_sha256}.tar.gz`) ||
      !Number.isInteger(artifact.size_bytes) ||
      artifact.size_bytes <= 0 ||
      artifact.size_bytes > this.config.maxArtifactBytes ||
      !ALLOWED_CONTENT_TYPES.has(artifact.content_type)
    ) {
      throw failure('SANDBOX_RESULT_INVALID', { retryable: false, httpStatus: 502 });
    }
    return {
      object_key: artifact.object_key,
      checksum_sha256: artifact.checksum_sha256,
      size_bytes: artifact.size_bytes,
      content_type: artifact.content_type,
    };
  }
}
