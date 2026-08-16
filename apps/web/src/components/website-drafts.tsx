'use client';

import { Notice, StatusBadge } from '@zylora/ui';
import { ArrowRight, Bot, LayoutTemplate, Plus, Sparkles, X } from 'lucide-react';
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';

import { apiRequest } from '@/lib/api';
import { PublishControls } from './publish-controls';
import { WebsiteExitControls } from './website-exit-controls';
import styles from './template-platform.module.css';

type Website = {
  id: string;
  display_name: string;
  status: string;
  pages: Array<{
    id: string;
    name: string;
    path: string;
    is_home: boolean;
    show_in_navigation: boolean;
  }>;
  created_at: string;
};

export function NewWebsiteModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const handleEscape = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    },
    [onClose],
  );
  useEffect(() => {
    if (!isOpen) return;
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isOpen, handleEscape]);

  if (!isOpen) return null;

  return (
    <div
      className="z-modal-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="new-website-modal-title"
    >
      <div className="z-modal-card" onClick={(e) => e.stopPropagation()}>
        <header className="z-modal-header">
          <div>
            <p className="eyebrow" style={{ margin: '0 0 0.3rem', color: 'var(--z-color-brand)' }}>
              Start your next project
            </p>
            <h2
              id="new-website-modal-title"
              style={{ margin: 0, fontSize: '1.4rem', fontWeight: 600 }}
            >
              Create New Website
            </h2>
          </div>
          <button
            className="z-modal-close"
            onClick={onClose}
            aria-label="Close modal"
            type="button"
          >
            <X size={18} />
          </button>
        </header>
        <div
          className="z-modal-body"
          style={{ display: 'grid', gap: '1rem', padding: '1.25rem 0 0.5rem' }}
        >
          <Link
            href="/app/templates"
            onClick={onClose}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              padding: '1.2rem',
              borderRadius: 'var(--z-radius-md)',
              background: 'var(--z-color-surface-subtle)',
              border: '1px solid var(--z-color-border)',
              color: 'var(--z-color-ink)',
              textDecoration: 'none',
              transition: 'all 180ms ease-out',
            }}
            className="creation-path-card"
          >
            <div
              style={{
                display: 'grid',
                width: '2.75rem',
                height: '2.75rem',
                placeItems: 'center',
                borderRadius: 'var(--z-radius-md)',
                background: 'rgba(16, 185, 129, 0.15)',
                color: 'var(--z-color-brand)',
                flexShrink: 0,
              }}
            >
              <LayoutTemplate size={22} />
            </div>
            <div style={{ flex: 1 }}>
              <strong style={{ display: 'block', fontSize: '0.95rem', marginBottom: '0.2rem' }}>
                Start from a Template
              </strong>
              <span style={{ fontSize: '0.8rem', color: 'var(--z-color-ink-muted)' }}>
                Browse approved responsive starting points created for real business categories.
              </span>
            </div>
            <ArrowRight size={18} style={{ color: 'var(--z-color-brand)' }} />
          </Link>

          <Link
            href="/app/ai-builder"
            onClick={onClose}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              padding: '1.2rem',
              borderRadius: 'var(--z-radius-md)',
              background: 'var(--z-color-surface-subtle)',
              border: '1px solid var(--z-color-border)',
              color: 'var(--z-color-ink)',
              textDecoration: 'none',
              transition: 'all 180ms ease-out',
            }}
            className="creation-path-card"
          >
            <div
              style={{
                display: 'grid',
                width: '2.75rem',
                height: '2.75rem',
                placeItems: 'center',
                borderRadius: 'var(--z-radius-md)',
                background: 'rgba(16, 185, 129, 0.12)',
                color: 'var(--z-color-brand)',
                flexShrink: 0,
              }}
            >
              <Bot size={22} />
            </div>
            <div style={{ flex: 1 }}>
              <strong style={{ display: 'block', fontSize: '0.95rem', marginBottom: '0.2rem' }}>
                Create with AI
              </strong>
              <span style={{ fontSize: '0.8rem', color: 'var(--z-color-ink-muted)' }}>
                Describe your business vision and let Zylora draft structured pages automatically.
              </span>
            </div>
            <Sparkles size={18} style={{ color: 'var(--z-color-brand)' }} />
          </Link>
        </div>
      </div>
    </div>
  );
}

type DraftSuggestion = {
  id: string;
  display_name: string;
  last_modified_at: string;
  site_origin: string;
};

type WebsiteListResponse = {
  items: Website[];
  total_drafts: number;
  draft_limit: number;
  warning?: string | null;
  suggested_removal?: DraftSuggestion | null;
};

export function WebsiteDrafts() {
  const [data, setData] = useState<WebsiteListResponse | null>(null);
  const [error, setError] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchWebsites = useCallback(() => {
    void apiRequest<WebsiteListResponse>('/api/v1/websites')
      .then((res) => {
        setData(res);
        setError('');
      })
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : 'Drafts are unavailable.');
      });
  }, []);

  useEffect(() => {
    fetchWebsites();
  }, [fetchWebsites]);

  const handleDeleteDraft = async (websiteId: string, displayName: string) => {
    if (!window.confirm(`Are you sure you want to delete draft "${displayName}"?`)) {
      return;
    }
    setDeletingId(websiteId);
    try {
      await apiRequest(`/api/v1/websites/${websiteId}`, { method: 'DELETE' });
      await fetchWebsites();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Could not delete draft.');
    } finally {
      setDeletingId(null);
    }
  };

  if (error) {
    return (
      <Notice tone="danger" title="Drafts unavailable">
        {error}
      </Notice>
    );
  }

  if (!data) return <p role="status">Loading your Drafts…</p>;

  const items = data.items;
  const liveWebsite = items.find(
    (item) => item.status.toLowerCase() === 'published' || item.status.toLowerCase() === 'live',
  );
  const drafts = items.filter(
    (item) => item !== liveWebsite && item.status.toLowerCase() !== 'archived',
  );
  const totalDrafts = data.total_drafts || drafts.length;
  const atDraftCap = totalDrafts >= 10;

  return (
    <div className="websites-container" style={{ display: 'grid', gap: '2rem' }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
          borderBottom: '1px solid var(--z-color-border)',
          paddingBottom: '1.25rem',
        }}
      >
        <div>
          <h2 style={{ margin: 0, fontSize: '1.6rem', fontWeight: 600 }}>Websites Management</h2>
          <p
            style={{
              margin: '0.3rem 0 0',
              color: 'var(--z-color-ink-muted)',
              fontSize: '0.875rem',
            }}
          >
            Manage your live website and private drafts ({totalDrafts}/10 draft slots used). Up to
            one live website per account.
          </p>
        </div>
        <button
          className="z-button z-button--primary"
          type="button"
          disabled={atDraftCap}
          onClick={() => {
            if (atDraftCap) return;
            setModalOpen(true);
          }}
          style={{ minHeight: '2.6rem', padding: '0.6rem 1.1rem' }}
        >
          <Plus size={16} /> New Website
        </button>
      </header>

      {data.warning ? (
        <Notice tone={atDraftCap ? 'danger' : 'warning'} title="Draft slot usage">
          {data.warning}
        </Notice>
      ) : null}

      {atDraftCap && data.suggested_removal ? (
        <Notice tone="info" title="Suggested draft for removal">
          <p style={{ margin: '0 0 0.5rem' }}>
            You&apos;ve reached your 10-draft limit. Suggested for removal based on last edit time:
            <br />
            <strong>&quot;{data.suggested_removal.display_name}&quot;</strong> (Last edited:{' '}
            {new Date(data.suggested_removal.last_modified_at).toLocaleDateString()})
          </p>
          <button
            className="z-button z-button--secondary"
            type="button"
            onClick={() =>
              handleDeleteDraft(data.suggested_removal!.id, data.suggested_removal!.display_name)
            }
            disabled={deletingId === data.suggested_removal.id}
          >
            {deletingId === data.suggested_removal.id ? 'Deleting…' : 'Delete this draft'}
          </button>
        </Notice>
      ) : null}

      <NewWebsiteModal isOpen={modalOpen} onClose={() => setModalOpen(false)} />

      {items.length === 0 ? (
        <div className={styles.empty}>
          <h2>No Draft Websites yet</h2>
          <p>
            Start from an approved Template or use AI generation to create a complete private Draft.
            No plan or payment is required to draft.
          </p>
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginTop: '1.25rem' }}>
            <button
              className="z-button z-button--primary"
              onClick={() => setModalOpen(true)}
              type="button"
              disabled={atDraftCap}
            >
              <Plus size={16} /> New Website
            </button>
          </div>
        </div>
      ) : (
        <div className={styles.adminStack}>
          {liveWebsite && (
            <section style={{ display: 'grid', gap: '1rem' }}>
              <span className="eyebrow" style={{ margin: 0, color: 'var(--z-color-brand)' }}>
                Live Website
              </span>
              <article
                className={styles.adminTemplate}
                style={{ borderLeft: '3px solid var(--z-color-brand)' }}
              >
                <header>
                  <div>
                    <h2>{liveWebsite.display_name}</h2>
                    <p>{liveWebsite.pages.length} pages · Live on Production</p>
                  </div>
                  <StatusBadge tone="success">{liveWebsite.status}</StatusBadge>
                </header>
                <div
                  style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginTop: '1rem' }}
                >
                  <Link
                    className="z-button z-button--secondary"
                    href={'/app/websites/' + liveWebsite.id + '/edit'}
                  >
                    Manage pages
                  </Link>
                  <PublishControls websiteId={liveWebsite.id} status={liveWebsite.status} />
                  <WebsiteExitControls websiteId={liveWebsite.id} />
                </div>
              </article>
            </section>
          )}

          {drafts.length > 0 && (
            <section style={{ display: 'grid', gap: '1rem' }}>
              <span className="eyebrow" style={{ margin: 0 }}>
                Drafts ({drafts.length})
              </span>
              {drafts.map((item) => (
                <article className={styles.adminTemplate} key={item.id}>
                  <header>
                    <div>
                      <h2>{item.display_name}</h2>
                      <p>{item.pages.length} pages · Private Draft</p>
                    </div>
                    <StatusBadge tone="info">{item.status}</StatusBadge>
                  </header>
                  <div
                    style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginTop: '1rem' }}
                  >
                    <Link
                      className="z-button z-button--secondary"
                      href={'/app/websites/' + item.id + '/edit'}
                    >
                      Manage pages
                    </Link>
                    <PublishControls websiteId={item.id} status={item.status} />
                    <WebsiteExitControls websiteId={item.id} />
                    <button
                      className="z-button z-button--ghost"
                      type="button"
                      onClick={() => handleDeleteDraft(item.id, item.display_name)}
                      disabled={deletingId === item.id}
                      style={{ color: '#dc2626' }}
                    >
                      {deletingId === item.id ? 'Deleting…' : 'Delete draft'}
                    </button>
                  </div>
                </article>
              ))}
            </section>
          )}
        </div>
      )}
    </div>
  );
}
