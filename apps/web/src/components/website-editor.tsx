'use client';

import type { TemplateComponent, TemplateDocument } from '@zylora/template-schema';
import { TemplateRenderer } from '@zylora/template-schema';
import {
  History,
  BookOpenText,
  Laptop,
  Monitor,
  PanelsTopLeft,
  RotateCcw,
  Smartphone,
  Sparkles,
} from 'lucide-react';
import { type FormEvent, useEffect, useMemo, useState } from 'react';
import { Notice, StatusBadge } from '@zylora/ui';

import { apiRequest, csrfToken } from '@/lib/api';
import { PageManager } from './page-manager';
import { ChatbotKnowledgePanel } from './chatbot-knowledge-panel';
import styles from './website-editor.module.css';

type Revision = {
  id: string;
  revision: number;
  source: string;
  edit_summary: string;
  created_at: string;
};
export type EditorState = {
  website_id: string;
  display_name: string;
  status: string;
  revision: number;
  document: TemplateDocument;
  revisions: Revision[];
  credits: { balance: number; allowance: number; period_start: string; period_end: string };
};
type Mutation = EditorState & { source: string; summary: string; credits_used: number };
type Operation = Record<string, unknown> & { kind: string };
type Device = 'desktop' | 'tablet' | 'mobile';
const widths: Record<Device, string> = { desktop: '100%', tablet: '48rem', mobile: '24.375rem' };

function headers() {
  const token = csrfToken('zylora_user_csrf');
  return token ? { 'X-CSRF-Token': token } : {};
}

export function documentPageDatabaseId(id: string): string {
  const value = id.startsWith('p') ? id.slice(1) : id;
  if (!/^[0-9a-f]{32}$/i.test(value)) return '';
  return `${value.slice(0, 8)}-${value.slice(8, 12)}-${value.slice(12, 16)}-${value.slice(16, 20)}-${value.slice(20)}`;
}

function fields(component: TemplateComponent): Array<[string, string]> {
  return ['eyebrow', 'heading', 'body', 'text']
    .map((key) => [key, component.props[key]] as const)
    .filter((entry): entry is [string, string] => typeof entry[1] === 'string');
}

function ComponentEditor({
  component,
  busy,
  save,
}: {
  component: TemplateComponent;
  busy: boolean;
  save: (id: string, property: string, value: string) => void;
}) {
  const values = fields(component);
  if (!values.length) return null;
  return (
    <article className={styles.componentCard}>
      <strong>{component.type.replaceAll('_', ' ')}</strong>
      {values.map(([property, initial]) => (
        <label key={`${component.id}:${property}`}>
          {property}
          {property === 'body' || property === 'text' ? (
            <textarea
              defaultValue={initial}
              disabled={busy}
              rows={3}
              onBlur={(event) =>
                event.target.value !== initial && save(component.id, property, event.target.value)
              }
            />
          ) : (
            <input
              defaultValue={initial}
              disabled={busy}
              onBlur={(event) =>
                event.target.value !== initial && save(component.id, property, event.target.value)
              }
            />
          )}
        </label>
      ))}
      <small>Autosaves when you leave a field.</small>
    </article>
  );
}

function ContentEditor({ websiteId }: { websiteId: string }) {
  const [state, setState] = useState<EditorState | null>(null);
  const [pageId, setPageId] = useState('');
  const [device, setDevice] = useState<Device>('desktop');
  const [scope, setScope] = useState<'PAGE' | 'WEBSITE'>('PAGE');
  const [prompt, setPrompt] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('Autosave ready');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    let active = true;
    apiRequest<EditorState>(`/api/v1/websites/${websiteId}/editor`)
      .then((result) => {
        if (!active) return;
        setState(result);
        setPageId(
          result.document.pages.find((page) => page.is_home)?.id ??
            result.document.pages[0]?.id ??
            '',
        );
      })
      .catch(
        (reason) =>
          active && setError(reason instanceof Error ? reason.message : 'Editor unavailable.'),
      );
    return () => {
      active = false;
    };
  }, [websiteId]);

  const page = useMemo(
    () => state?.document.pages.find((item) => item.id === pageId),
    [pageId, state],
  );
  const databasePageId = page ? documentPageDatabaseId(page.id) : '';

  async function mutate(path: string, body: object) {
    setBusy(true);
    setStatus('Saving…');
    setError('');
    setMessage('');
    try {
      const result = await apiRequest<Mutation>(path, {
        method: 'POST',
        body: JSON.stringify(body),
        headers: headers(),
      });
      setState(result);
      setStatus('Saved');
      setMessage(
        result.source === 'AI'
          ? `${result.summary} · ${result.credits_used} credit${result.credits_used === 1 ? '' : 's'} used.`
          : result.summary,
      );
      return result;
    } catch (reason) {
      setStatus('Not saved');
      setError(reason instanceof Error ? reason.message : 'The edit could not be applied.');
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function manual(
    operations: Operation[],
    summary: string,
    editScope: 'PAGE' | 'WEBSITE' = 'PAGE',
  ) {
    if (!state) return;
    await mutate(`/api/v1/websites/${websiteId}/editor/edits`, {
      operation_id: crypto.randomUUID(),
      base_revision: state.revision,
      scope: editScope,
      selected_page_id: editScope === 'PAGE' ? databasePageId : null,
      summary,
      operations,
    });
  }

  function saveComponent(componentId: string, property: string, value: string) {
    void manual(
      [
        {
          kind: 'SET_COMPONENT_PROP',
          page_id: databasePageId,
          component_id: componentId,
          property,
          value,
        },
      ],
      `Updated ${property} on ${page?.label ?? 'page'}`,
    );
  }

  async function submitAi(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!state || !prompt.trim()) return;
    const result = await mutate(`/api/v1/websites/${websiteId}/editor/ai-edits`, {
      operation_id: crypto.randomUUID(),
      base_revision: state.revision,
      prompt: prompt.trim(),
      scope,
      selected_page_id: scope === 'PAGE' ? databasePageId : null,
    });
    if (result) setPrompt('');
  }

  async function restore(revision: Revision) {
    if (!state || revision.revision === state.revision) return;
    await mutate(`/api/v1/websites/${websiteId}/editor/versions/${revision.id}/restore`, {
      operation_id: crypto.randomUUID(),
      base_revision: state.revision,
    });
  }

  if (error && !state)
    return (
      <Notice tone="danger" title="Website editor unavailable">
        {error}
      </Notice>
    );
  if (!state) return <p role="status">Loading structured Website editor…</p>;

  return (
    <div className={styles.workspace}>
      <header className={styles.header}>
        <div>
          <p>Structured Website editor</p>
          <h1>{state.display_name}</h1>
        </div>
        <div className={styles.meta}>
          <StatusBadge tone="info">{state.status}</StatusBadge>
          <span>Revision {state.revision}</span>
          <span>{status}</span>
          <span>{state.credits.balance} AI credits</span>
        </div>
      </header>
      {(message || error) && (
        <div className={error ? styles.error : styles.feedback}>{error || message}</div>
      )}

      <div className={styles.grid}>
        <aside className={styles.controls}>
          <section>
            <p className={styles.eyebrow}>Current page</p>
            <label>
              Page to edit
              <select value={pageId} onChange={(event) => setPageId(event.target.value)}>
                {state.document.pages.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.is_home ? '/' : `/${item.slug}`} · {item.label}
                  </option>
                ))}
              </select>
            </label>
          </section>
          <section>
            <p className={styles.eyebrow}>AI editing</p>
            <div className={styles.credits}>
              <strong>{state.credits.balance}</strong>
              <span>of {state.credits.allowance} monthly credits remain</span>
            </div>
            <form onSubmit={submitAi}>
              <label>
                Change scope
                <select
                  value={scope}
                  onChange={(event) => setScope(event.target.value as typeof scope)}
                >
                  <option value="PAGE">This page only</option>
                  <option value="WEBSITE">Entire Website / page graph</option>
                </select>
              </label>
              <label>
                Tell Zylora what to change
                <textarea
                  maxLength={1200}
                  placeholder={
                    scope === 'PAGE'
                      ? 'Rewrite this page to feel more premium.'
                      : 'Add an FAQ page under Resources and show it in navigation.'
                  }
                  required
                  rows={5}
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                />
              </label>
              <button disabled={busy || state.credits.balance === 0} type="submit">
                <Sparkles size={16} /> {busy ? 'Planning safely…' : 'Plan and apply change'}
              </button>
              <small>
                AI validates first, applies atomically, then records a recoverable revision.
              </small>
            </form>
          </section>
          <section>
            <p className={styles.eyebrow}>Theme</p>
            <div className={styles.theme}>
              {(['primary', 'accent', 'surface', 'ink'] as const).map((property) => (
                <label key={property}>
                  {property}
                  <input
                    type="color"
                    value={state.document.theme[property]}
                    onChange={(event) =>
                      void manual(
                        [
                          {
                            kind: 'SET_THEME_TOKEN',
                            property,
                            value: event.target.value.toUpperCase(),
                          },
                        ],
                        `Updated Website ${property}`,
                        'WEBSITE',
                      )
                    }
                  />
                </label>
              ))}
            </div>
          </section>
        </aside>

        <main className={styles.canvas}>
          <div className={styles.toolbar}>
            <div>
              <strong>{page?.label}</strong>
              <span>{page?.is_home ? '/' : `/${page?.slug}`}</span>
            </div>
            <div aria-label="Preview width">
              {(
                [
                  ['desktop', Monitor],
                  ['tablet', Laptop],
                  ['mobile', Smartphone],
                ] as const
              ).map(([value, Icon]) => (
                <button
                  key={value}
                  aria-label={`${value} preview`}
                  aria-pressed={device === value}
                  onClick={() => setDevice(value)}
                  type="button"
                >
                  <Icon size={16} />
                </button>
              ))}
            </div>
          </div>
          <div className={styles.preview}>
            <div style={{ width: widths[device] }}>
              <TemplateRenderer document={state.document} page={page?.slug ?? 'home'} />
            </div>
          </div>
        </main>

        <aside className={styles.settings}>
          <section>
            <p className={styles.eyebrow}>Page content</p>
            <h2>{page?.label}</h2>
            <p>Manual and AI changes use this same structured document.</p>
            <div className={styles.components}>
              {page?.components.map((component) => (
                <ComponentEditor
                  key={`${state.revision}:${component.id}`}
                  component={component}
                  busy={busy}
                  save={saveComponent}
                />
              ))}
            </div>
          </section>
          <section>
            <p className={styles.eyebrow}>Revision history</p>
            <div className={styles.history}>
              {state.revisions.map((revision) => (
                <div key={revision.id}>
                  <History size={15} />
                  <span>
                    <strong>Revision {revision.revision}</strong>
                    <small>{revision.edit_summary}</small>
                  </span>
                  <button
                    aria-label={`Restore revision ${revision.revision}`}
                    disabled={busy || revision.revision === state.revision}
                    onClick={() => void restore(revision)}
                    type="button"
                  >
                    <RotateCcw size={14} />
                  </button>
                </div>
              ))}
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}

export function WebsiteEditor({ websiteId }: { websiteId: string }) {
  const [view, setView] = useState<'CONTENT' | 'STRUCTURE' | 'KNOWLEDGE'>('STRUCTURE');
  return (
    <div className={styles.root}>
      <nav className={styles.tabs} aria-label="Website editor views">
        <button aria-pressed={view === 'CONTENT'} type="button" onClick={() => setView('CONTENT')}>
          <Sparkles size={16} /> Content & AI
        </button>
        <button
          aria-pressed={view === 'STRUCTURE'}
          type="button"
          onClick={() => setView('STRUCTURE')}
        >
          <PanelsTopLeft size={16} /> Pages & navigation
        </button>
        <button
          aria-pressed={view === 'KNOWLEDGE'}
          type="button"
          onClick={() => setView('KNOWLEDGE')}
        >
          <BookOpenText size={16} /> Chatbot &amp; Knowledge
        </button>
      </nav>
      {view === 'KNOWLEDGE' ? (
        <ChatbotKnowledgePanel websiteId={websiteId} />
      ) : view === 'CONTENT' ? (
        <ContentEditor websiteId={websiteId} />
      ) : (
        <PageManager websiteId={websiteId} />
      )}
    </div>
  );
}
