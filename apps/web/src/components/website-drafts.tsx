'use client';

import { Notice, StatusBadge } from '@zylora/ui';
import {
  ArrowRight,
  Bot,
  LayoutTemplate,
  Plus,
  Radio,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';
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
  site_origin?: string;
  custom_domain?: string | null;
  subdomain?: string | null;
  pages: Array<{
    id: string;
    name: string;
    path: string;
    is_home: boolean;
    show_in_navigation: boolean;
  }>;
  created_at: string;
  updated_at?: string;
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
              style={{ margin: 0, fontSize: '1.4rem', fontWeight: 600, color: '#ffffff' }}
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
              padding: '1.25rem',
              borderRadius: 'var(--z-radius-lg)',
              background: 'var(--z-color-surface-raised)',
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
                width: '3rem',
                height: '3rem',
                placeItems: 'center',
                borderRadius: 'var(--z-radius-md)',
                background: 'var(--z-color-brand-soft)',
                color: 'var(--z-color-brand)',
                border: '1px solid rgba(212, 255, 50, 0.2)',
                flexShrink: 0,
              }}
            >
              <LayoutTemplate size={22} />
            </div>
            <div style={{ flex: 1 }}>
              <strong
                style={{
                  display: 'block',
                  fontSize: '1rem',
                  marginBottom: '0.25rem',
                  color: '#ffffff',
                }}
              >
                Start from a Template
              </strong>
              <span style={{ fontSize: '0.8125rem', color: 'var(--z-color-ink-muted)' }}>
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
              padding: '1.25rem',
              borderRadius: 'var(--z-radius-lg)',
              background: 'var(--z-color-surface-raised)',
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
                width: '3rem',
                height: '3rem',
                placeItems: 'center',
                borderRadius: 'var(--z-radius-md)',
                background: 'rgba(56, 189, 248, 0.12)',
                color: 'var(--z-color-info)',
                border: '1px solid rgba(56, 189, 248, 0.25)',
                flexShrink: 0,
              }}
            >
              <Bot size={22} />
            </div>
            <div style={{ flex: 1 }}>
              <strong
                style={{
                  display: 'block',
                  fontSize: '1rem',
                  marginBottom: '0.25rem',
                  color: '#ffffff',
                }}
              >
                Create with AI
              </strong>
              <span style={{ fontSize: '0.8125rem', color: 'var(--z-color-ink-muted)' }}>
                Describe your business vision and let Zylora draft structured pages automatically.
              </span>
            </div>
            <Sparkles size={18} style={{ color: 'var(--z-color-info)' }} />
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
  const [confirmDeleteWebsite, setConfirmDeleteWebsite] = useState<{
    id: string;
    name: string;
  } | null>(null);

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

  const handleDeleteDraft = async (websiteId: string) => {
    setDeletingId(websiteId);
    try {
      await apiRequest(`/api/v1/websites/${websiteId}`, { method: 'DELETE' });
      setConfirmDeleteWebsite(null);
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
  const draftLimit = data.draft_limit || 10;
  const atDraftCap = totalDrafts >= draftLimit;
  const usagePercentage = Math.min(100, (totalDrafts / draftLimit) * 100);

  return (
    <div className="websites-container" style={{ display: 'grid', gap: '1.75rem' }}>
      {/* Draft Cap & Command Center Header */}
      <section
        style={{
          border: '1px solid var(--z-color-border)',
          borderRadius: 'var(--z-radius-lg)',
          background: 'var(--z-color-surface)',
          padding: '1.5rem',
          boxShadow: 'var(--z-shadow-card)',
          display: 'grid',
          gap: '1.25rem',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '1rem',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <span className="workspace-kicker" style={{ margin: 0 }}>
                Fleet Overview
              </span>
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                  padding: '0.2rem 0.55rem',
                  borderRadius: 'var(--z-radius-round)',
                  background: 'var(--z-color-surface-raised)',
                  border: '1px solid var(--z-color-border)',
                  fontSize: '0.6875rem',
                  fontFamily: 'var(--z-font-mono)',
                  color:
                    totalDrafts >= 10
                      ? 'var(--z-color-danger)'
                      : totalDrafts >= 8
                        ? 'var(--z-color-warning)'
                        : 'var(--z-color-brand)',
                }}
              >
                Slots: {totalDrafts}/{draftLimit}
              </span>
            </div>
            <h2
              style={{
                margin: '0.35rem 0 0',
                fontSize: '1.5rem',
                fontWeight: 600,
                color: '#ffffff',
                letterSpacing: '-0.03em',
              }}
            >
              Websites & Private Drafts
            </h2>
          </div>
          <button
            className="z-button z-button--primary"
            type="button"
            disabled={atDraftCap}
            onClick={() => {
              if (atDraftCap) return;
              setModalOpen(true);
            }}
          >
            <Plus size={16} /> New Website
          </button>
        </div>

        {/* Draft Usage Progress Bar */}
        <div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '0.45rem',
              fontSize: '0.75rem',
              color: 'var(--z-color-ink-muted)',
            }}
          >
            <span>Draft Slot Capacity</span>
            <span>
              {totalDrafts} of {draftLimit} private drafts in use ({liveWebsite ? '1 Live' : '0 Live'})
            </span>
          </div>
          <div
            style={{
              height: '0.5rem',
              borderRadius: 'var(--z-radius-round)',
              background: 'var(--z-color-surface-subtle)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                height: '100%',
                width: `${usagePercentage}%`,
                borderRadius: 'var(--z-radius-round)',
                background:
                  totalDrafts >= 10
                    ? 'var(--z-color-danger)'
                    : totalDrafts >= 8
                      ? 'var(--z-color-warning)'
                      : 'var(--z-color-brand)',
                transition: 'width 240ms ease-out',
                boxShadow:
                  totalDrafts >= 8
                    ? '0 0 10px rgba(251, 191, 36, 0.4)'
                    : '0 0 10px rgba(212, 255, 50, 0.4)',
              }}
            />
          </div>
        </div>
      </section>

      {data.warning ? (
        <Notice tone={atDraftCap ? 'danger' : 'warning'} title="Draft slot warning">
          {data.warning}
        </Notice>
      ) : null}

      {atDraftCap && data.suggested_removal ? (
        <Notice tone="info" title="Draft limit reached (10/10)">
          <p style={{ margin: '0 0 0.65rem' }}>
            You have reached the maximum allowed 10 private drafts. To create new projects, remove
            an unused draft.
            <br />
            <strong>Suggested draft for removal:</strong> &quot;{data.suggested_removal.display_name}&quot; (Last edited:{' '}
            {new Date(data.suggested_removal.last_modified_at).toLocaleDateString()})
          </p>
          <button
            className="z-button z-button--danger"
            type="button"
            onClick={() =>
              setConfirmDeleteWebsite({
                id: data.suggested_removal!.id,
                name: data.suggested_removal!.display_name,
              })
            }
            disabled={deletingId === data.suggested_removal.id}
          >
            {deletingId === data.suggested_removal.id ? 'Deleting…' : 'Delete suggested draft'}
          </button>
        </Notice>
      ) : null}

      <NewWebsiteModal isOpen={modalOpen} onClose={() => setModalOpen(false)} />

      {/* Delete Confirmation Modal */}
      {confirmDeleteWebsite && (
        <div
          className="z-modal-overlay"
          onClick={() => setConfirmDeleteWebsite(null)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-modal-title"
        >
          <div className="z-modal-card" onClick={(e) => e.stopPropagation()}>
            <header className="z-modal-header">
              <div>
                <p className="eyebrow" style={{ color: 'var(--z-color-danger)', margin: '0 0 0.3rem' }}>
                  Permanent Action
                </p>
                <h2 id="delete-modal-title" style={{ margin: 0, fontSize: '1.35rem', color: '#ffffff' }}>
                  Delete Draft Project
                </h2>
              </div>
              <button
                className="z-modal-close"
                onClick={() => setConfirmDeleteWebsite(null)}
                aria-label="Close modal"
                type="button"
              >
                <X size={18} />
              </button>
            </header>
            <div style={{ padding: '1.25rem 0' }}>
              <p style={{ margin: 0, color: 'var(--z-color-ink-soft)', lineHeight: 1.6 }}>
                Are you sure you want to delete <strong>&quot;{confirmDeleteWebsite.name}&quot;</strong>? This
                private draft and its revision history will be permanently deleted.
              </p>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button
                className="z-button z-button--secondary"
                type="button"
                onClick={() => setConfirmDeleteWebsite(null)}
              >
                Cancel
              </button>
              <button
                className="z-button z-button--danger"
                type="button"
                onClick={() => handleDeleteDraft(confirmDeleteWebsite.id)}
                disabled={deletingId === confirmDeleteWebsite.id}
              >
                {deletingId === confirmDeleteWebsite.id ? 'Deleting…' : 'Confirm Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

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
        <div style={{ display: 'grid', gap: '2rem' }}>
          {/* LIVE WEBSITE HERO CARD */}
          {liveWebsite && (
            <section style={{ display: 'grid', gap: '0.85rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Radio size={14} style={{ color: 'var(--z-color-success)' }} />
                <span className="workspace-kicker" style={{ margin: 0, color: 'var(--z-color-success)' }}>
                  Active Live Website
                </span>
              </div>
              <article
                style={{
                  border: '1px solid rgba(16, 185, 129, 0.35)',
                  borderRadius: 'var(--z-radius-lg)',
                  background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, var(--z-color-surface) 60%)',
                  padding: '1.5rem',
                  boxShadow: '0 8px 30px rgba(0, 0, 0, 0.5), 0 0 20px rgba(16, 185, 129, 0.08)',
                  display: 'grid',
                  gap: '1.25rem',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '1rem',
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                      <h3
                        style={{
                          margin: 0,
                          fontSize: '1.45rem',
                          fontWeight: 700,
                          color: '#ffffff',
                          letterSpacing: '-0.03em',
                        }}
                      >
                        {liveWebsite.display_name}
                      </h3>
                      <StatusBadge tone="success">LIVE</StatusBadge>
                      <span
                        style={{
                          padding: '0.2rem 0.5rem',
                          borderRadius: 'var(--z-radius-round)',
                          background: 'var(--z-color-surface-raised)',
                          border: '1px solid var(--z-color-border)',
                          fontSize: '0.6875rem',
                          color: 'var(--z-color-ink-muted)',
                        }}
                      >
                        {liveWebsite.site_origin === 'AI' ? 'AI Origin' : 'Template Origin'}
                      </span>
                    </div>
                    <p
                      style={{
                        margin: '0.45rem 0 0',
                        color: 'var(--z-color-ink-muted)',
                        fontSize: '0.8125rem',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.85rem',
                      }}
                    >
                      <span>{liveWebsite.pages.length} Pages</span>
                      <span>•</span>
                      <span>Verified Deployment</span>
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '0.65rem', flexWrap: 'wrap' }}>
                    <Link
                      className="z-button z-button--primary"
                      href={'/app/websites/' + liveWebsite.id + '/edit'}
                    >
                      Edit Website
                    </Link>
                  </div>
                </div>

                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.75rem',
                    flexWrap: 'wrap',
                    borderTop: '1px solid var(--z-color-border)',
                    paddingTop: '1rem',
                  }}
                >
                  <PublishControls websiteId={liveWebsite.id} status={liveWebsite.status} />
                  <WebsiteExitControls websiteId={liveWebsite.id} />
                </div>
              </article>
            </section>
          )}

          {/* DRAFTS GRID */}
          {drafts.length > 0 && (
            <section style={{ display: 'grid', gap: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span className="workspace-kicker" style={{ margin: 0 }}>
                  Private Drafts ({drafts.length})
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--z-color-ink-muted)' }}>
                  {draftLimit - totalDrafts} slots remaining
                </span>
              </div>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(20rem, 1fr))',
                  gap: '1.25rem',
                }}
              >
                {drafts.map((item) => (
                  <article
                    key={item.id}
                    style={{
                      border: '1px solid var(--z-color-border)',
                      borderRadius: 'var(--z-radius-lg)',
                      background: 'var(--z-color-surface)',
                      padding: '1.25rem',
                      boxShadow: 'var(--z-shadow-card)',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      gap: '1.25rem',
                      transition: 'all var(--z-motion-fast) var(--z-ease-standard)',
                    }}
                  >
                    <div>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          justifyContent: 'space-between',
                          gap: '0.75rem',
                          marginBottom: '0.5rem',
                        }}
                      >
                        <h4
                          style={{
                            margin: 0,
                            fontSize: '1.15rem',
                            fontWeight: 700,
                            color: '#ffffff',
                            letterSpacing: '-0.02em',
                          }}
                        >
                          {item.display_name}
                        </h4>
                        <StatusBadge tone="info">{item.status}</StatusBadge>
                      </div>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.5rem',
                          flexWrap: 'wrap',
                          fontSize: '0.75rem',
                          color: 'var(--z-color-ink-muted)',
                        }}
                      >
                        <span
                          style={{
                            padding: '0.15rem 0.45rem',
                            borderRadius: 'var(--z-radius-sm)',
                            background: 'var(--z-color-surface-raised)',
                            border: '1px solid var(--z-color-border)',
                            color: 'var(--z-color-ink-soft)',
                          }}
                        >
                          {item.site_origin === 'AI' ? 'AI Origin' : 'Template Origin'}
                        </span>
                        <span>{item.pages.length} Pages</span>
                      </div>
                    </div>

                    <div
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.65rem',
                        borderTop: '1px solid var(--z-color-border)',
                        paddingTop: '0.85rem',
                      }}
                    >
                      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <Link
                          className="z-button z-button--secondary"
                          href={'/app/websites/' + item.id + '/edit'}
                          style={{ flex: 1, minHeight: '2.35rem', fontSize: '0.75rem' }}
                        >
                          Edit
                        </Link>
                        <PublishControls websiteId={item.id} status={item.status} />
                        <button
                          className="z-button z-button--quiet"
                          type="button"
                          onClick={() =>
                            setConfirmDeleteWebsite({
                              id: item.id,
                              name: item.display_name,
                            })
                          }
                          disabled={deletingId === item.id}
                          style={{ minHeight: '2.35rem', padding: '0 0.6rem' }}
                          title="Delete draft"
                          aria-label={`Delete ${item.display_name}`}
                        >
                          <Trash2 size={15} style={{ color: 'var(--z-color-danger)' }} />
                        </button>
                      </div>
                      <WebsiteExitControls websiteId={item.id} />
                    </div>
                  </article>
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
