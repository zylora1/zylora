'use client';

import {
  ArrowRight,
  Check,
  Code2,
  Eye,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react';
import { FormEvent, useEffect, useState } from 'react';

import { apiRequest, csrfToken } from '@/lib/api';
import { AI_PROMPT_STORAGE_KEY, storedAiPrompt } from '@/lib/ai-builder';
import styles from './ai-builder-project.module.css';

type Project = {
  id: string;
  status: string;
  generation_id: string;
  generation_version: number;
  attempt: number;
  max_attempts: number;
  retryable: boolean;
  can_cancel: boolean;
  can_retry: boolean;
  preview_ready: boolean;
  artifact_digest: string | null;
  safe_error_code: string | null;
  safe_error_message: string | null;
  queued_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
  cancelled_at: string | null;
  created_at: string;
  updated_at: string;
};

type ProjectList = { items: Project[] };
type ArtifactAccess = { download_url: string };

const ACTIVE_STATES = [
  'CREATED',
  'QUEUED',
  'CLAIMED',
  'GENERATING',
  'VALIDATING',
  'SCANNING',
  'SANDBOXING',
  'BUILDING',
  'STORING',
];

const STATE_LABELS: Record<string, string> = {
  CREATED: 'Created',
  QUEUED: 'Queued',
  CLAIMED: 'Starting',
  GENERATING: 'Generating',
  VALIDATING: 'Validating',
  SCANNING: 'Security scan',
  SANDBOXING: 'Sandboxing',
  BUILDING: 'Building',
  STORING: 'Storing',
  COMPLETED: 'Preview ready',
  FAILED: 'Failed',
  CANCELLED: 'Cancelled',
};

export function AiBuilderProject() {
  const [prompt, setPrompt] = useState('');
  const [projects, setProjects] = useState<Project[]>([]);
  const [pending, setPending] = useState(false);
  const [actionId, setActionId] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    void Promise.resolve().then(() => setPrompt(storedAiPrompt()));
    void apiRequest<ProjectList>('/api/v1/ai-site-projects')
      .then((result) => setProjects(result.items))
      .catch(() => setProjects([]));
  }, []);

  useEffect(() => {
    const active = projects.filter((project) => ACTIVE_STATES.includes(project.status));
    if (!active.length) return;
    const timer = window.setTimeout(() => {
      void Promise.all(
        active.map((project) =>
          apiRequest<Project>(`/api/v1/ai-site-projects/${project.id}`).catch(() => project),
        ),
      ).then((updates) => {
        const byId = new Map(updates.map((project) => [project.id, project]));
        setProjects((current) => current.map((project) => byId.get(project.id) ?? project));
      });
    }, 5000);
    return () => window.clearTimeout(timer);
  }, [projects]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError('');
    setNotice('');
    try {
      const project = await apiRequest<Project>('/api/v1/ai-site-projects', {
        method: 'POST',
        headers: {
          'X-CSRF-Token': csrfToken('zylora_user_csrf') ?? '',
          'Idempotency-Key': `ai-site-${crypto.randomUUID()}`,
        },
        body: JSON.stringify({ prompt: prompt.trim() }),
      });
      window.sessionStorage.removeItem(AI_PROMPT_STORAGE_KEY);
      setPrompt('');
      updateProject(project);
      setNotice('Your durable generation is queued. You can leave or refresh this page safely.');
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : 'The AI website project could not be queued.',
      );
    } finally {
      setPending(false);
    }
  }

  async function projectAction(project: Project, action: 'cancel' | 'retry') {
    setActionId(project.id);
    setError('');
    try {
      const updated = await apiRequest<Project>(
        `/api/v1/ai-site-projects/${project.id}/${action}`,
        {
          method: 'POST',
          headers: {
            'X-CSRF-Token': csrfToken('zylora_user_csrf') ?? '',
            ...(action === 'retry' ? { 'Idempotency-Key': `ai-retry-${crypto.randomUUID()}` } : {}),
          },
        },
      );
      updateProject(updated);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : `The generation could not ${action}.`);
    } finally {
      setActionId('');
    }
  }

  async function openPreview(project: Project) {
    setActionId(project.id);
    setError('');
    try {
      const access = await apiRequest<ArtifactAccess>(
        `/api/v1/ai-site-projects/${project.id}/generations/${project.generation_id}/artifact`,
      );
      window.open(access.download_url, '_blank', 'noopener,noreferrer');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The preview artifact is unavailable.');
    } finally {
      setActionId('');
    }
  }

  function updateProject(project: Project) {
    setProjects((current) => [project, ...current.filter((item) => item.id !== project.id)]);
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <p>ZYLORA AI</p>
        <h1>Describe the website. Keep control of the outcome.</h1>
        <span>
          Zylora creates a separate production website build. Your Template drafts stay untouched.
        </span>
      </header>
      <div className={styles.layout}>
        <form className={styles.composer} onSubmit={submit}>
          <label htmlFor="ai-site-prompt">What should this website accomplish?</label>
          <textarea
            id="ai-site-prompt"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            minLength={20}
            maxLength={2000}
            rows={9}
            placeholder="A premium dental clinic website for families in Bengaluru. Include treatments, the doctors, clinic location, FAQs, and a clear appointment enquiry path."
            required
          />
          <div className={styles.promptMeta}>
            <span>{prompt.length} / 2,000</span>
            <span>Do not include passwords, credentials, or private customer data.</span>
          </div>
          {error ? (
            <p className={styles.error} role="alert">
              {error}
            </p>
          ) : null}
          {notice ? (
            <p className={styles.notice} role="status">
              {notice}
            </p>
          ) : null}
          <button type="submit" disabled={pending || prompt.trim().length < 20}>
            {pending ? (
              <LoaderCircle className={styles.spinner} aria-hidden="true" size={17} />
            ) : (
              <Sparkles aria-hidden="true" size={17} />
            )}
            {pending ? 'Queuing securely...' : 'Build this website'}
            {!pending ? <ArrowRight aria-hidden="true" size={16} /> : null}
          </button>
        </form>
        <aside className={styles.boundary}>
          <div>
            <Code2 aria-hidden="true" />
            <h2>A real Next.js website</h2>
            <p>Generated as a separate project rather than forced into the Template renderer.</p>
          </div>
          <div>
            <ShieldCheck aria-hidden="true" />
            <h2>Built outside Zylora Core</h2>
            <p>
              Generated code never runs beside identity, billing, database, or platform secrets.
            </p>
          </div>
          <ul>
            {[
              'Requirements and site plan',
              'Responsive TypeScript output',
              'Build and browser checks',
              'Immutable artifact on success',
            ].map((item) => (
              <li key={item}>
                <Check aria-hidden="true" size={13} /> {item}
              </li>
            ))}
          </ul>
        </aside>
      </div>
      <section className={styles.projects} aria-labelledby="ai-projects-title">
        <div>
          <p>BUILD QUEUE</p>
          <h2 id="ai-projects-title">Your AI website projects</h2>
        </div>
        {projects.length ? (
          <div className={styles.projectList}>
            {projects.map((project) => (
              <article key={project.id}>
                <div>
                  <span>AI website · version {project.generation_version}</span>
                  <small>
                    {new Date(project.created_at).toLocaleDateString()} · attempt {project.attempt}{' '}
                    of {project.max_attempts}
                  </small>
                  {project.safe_error_message ? <small>{project.safe_error_message}</small> : null}
                </div>
                <b data-status={project.status}>{STATE_LABELS[project.status] ?? project.status}</b>
                <div className={styles.actions}>
                  {project.preview_ready ? (
                    <button type="button" onClick={() => void openPreview(project)}>
                      <Eye aria-hidden="true" size={13} /> Open artifact
                    </button>
                  ) : null}
                  {project.can_retry ? (
                    <button
                      type="button"
                      onClick={() => void projectAction(project, 'retry')}
                      disabled={actionId === project.id}
                    >
                      <RefreshCw aria-hidden="true" size={13} /> Retry
                    </button>
                  ) : null}
                  {project.can_cancel ? (
                    <button
                      type="button"
                      onClick={() => void projectAction(project, 'cancel')}
                      disabled={actionId === project.id}
                    >
                      <X aria-hidden="true" size={13} /> Cancel
                    </button>
                  ) : null}
                  <code>{project.generation_id.slice(0, 16)}</code>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className={styles.empty}>
            No AI website projects yet. Your first accepted request will appear here.
          </p>
        )}
      </section>
    </div>
  );
}
