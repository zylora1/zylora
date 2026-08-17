'use client';

import { Notice, StatusBadge } from '@zylora/ui';
import {
  Kanban,
  List,
  Mail,
  Search,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { apiRequest } from '@/lib/api';

type Website = { id: string; display_name: string; status: string };
type Lead = {
  id: string;
  source: string;
  name: string;
  email: string | null;
  phone: string | null;
  enquiry: string;
  page_path: string | null;
  status: string;
  captured_at: string;
};
type LeadCredits = { balance: number; policy: string };

export function LeadsPanel() {
  const [websites, setWebsites] = useState<Website[] | null>(null);
  const [selectedWebsiteId, setSelectedWebsiteId] = useState('');
  const [leads, setLeads] = useState<Lead[] | null>(null);
  const [credits, setCredits] = useState<LeadCredits | null>(null);
  const [error, setError] = useState('');
  const [viewMode, setViewMode] = useState<'board' | 'list'>('board');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    void Promise.resolve().then(async () => {
      try {
        const [websiteResponse, creditResponse] = await Promise.all([
          apiRequest<{ items: Website[] }>('/api/v1/websites'),
          apiRequest<LeadCredits>('/api/v1/lead-credits'),
        ]);
        setWebsites(websiteResponse.items);
        setCredits(creditResponse);
        setSelectedWebsiteId(websiteResponse.items[0]?.id ?? '');
        if (websiteResponse.items.length === 0) setLeads([]);
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : 'Leads are unavailable.');
      }
    });
  }, []);

  useEffect(() => {
    if (!selectedWebsiteId) return;
    void Promise.resolve().then(async () => {
      try {
        setLeads(await apiRequest<Lead[]>(`/api/v1/websites/${selectedWebsiteId}/leads?limit=50`));
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : 'Leads are unavailable.');
      }
    });
  }, [selectedWebsiteId]);

  const filteredLeads = useMemo(() => {
    if (!leads) return [];
    if (!searchQuery.trim()) return leads;
    const q = searchQuery.toLowerCase();
    return leads.filter(
      (lead) =>
        lead.name.toLowerCase().includes(q) ||
        (lead.email && lead.email.toLowerCase().includes(q)) ||
        (lead.phone && lead.phone.toLowerCase().includes(q)) ||
        lead.enquiry.toLowerCase().includes(q),
    );
  }, [leads, searchQuery]);

  if (error) {
    return (
      <Notice tone="danger" title="Leads unavailable">
        {error}
      </Notice>
    );
  }
  if (!websites || !credits) return <p role="status">Loading Leads…</p>;
  if (websites.length === 0) {
    return (
      <Notice title="No Website selected">
        Leads appear here after you publish a Website and visitors explicitly submit its enquiry
        form.
      </Notice>
    );
  }
  if (!leads) return <p role="status">Loading Leads…</p>;

  return (
    <div className="leads-panel" style={{ display: 'grid', gap: '1.5rem' }}>
      {/* Top Operations Header */}
      <section
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(13rem, 1fr))',
          gap: '1rem',
        }}
      >
        <article
          style={{
            border: '1px solid var(--z-color-border)',
            borderRadius: 'var(--z-radius-lg)',
            background: 'var(--z-color-surface)',
            padding: '1.25rem 1.4rem',
            boxShadow: 'var(--z-shadow-card)',
          }}
        >
          <p className="workspace-kicker" style={{ margin: '0 0 0.35rem' }}>
            Current ledger balance
          </p>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.65rem' }}>
            <strong
              style={{
                fontFamily: 'var(--z-font-mono)',
                fontSize: '1.75rem',
                fontWeight: 750,
                color: '#ffffff',
              }}
            >
              {credits.balance}
            </strong>
            <span style={{ fontSize: '0.75rem', color: 'var(--z-color-ink-muted)' }}>Credits</span>
          </div>
          <p style={{ margin: '0.45rem 0 0', fontSize: '0.75rem', color: 'var(--z-color-ink-muted)' }}>
            1 valid Lead = 1 credit deducted
          </p>
        </article>

        <article
          style={{
            border: '1px solid var(--z-color-border)',
            borderRadius: 'var(--z-radius-lg)',
            background: 'var(--z-color-surface)',
            padding: '1.25rem 1.4rem',
            boxShadow: 'var(--z-shadow-card)',
          }}
        >
          <p className="workspace-kicker" style={{ margin: '0 0 0.35rem' }}>
            Captured Enquiries
          </p>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.65rem' }}>
            <strong
              style={{
                fontFamily: 'var(--z-font-mono)',
                fontSize: '1.75rem',
                fontWeight: 750,
                color: 'var(--z-color-brand)',
              }}
            >
              {leads.length}
            </strong>
            <span style={{ fontSize: '0.75rem', color: 'var(--z-color-ink-muted)' }}>Total</span>
          </div>
          <p style={{ margin: '0.45rem 0 0', fontSize: '0.75rem', color: 'var(--z-color-ink-muted)' }}>
            From published website enquiry forms
          </p>
        </article>

        <article
          style={{
            border: '1px solid var(--z-color-border)',
            borderRadius: 'var(--z-radius-lg)',
            background: 'var(--z-color-surface)',
            padding: '1.25rem 1.4rem',
            boxShadow: 'var(--z-shadow-card)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <p className="workspace-kicker" style={{ margin: '0 0 0.35rem' }}>
            Credit Policy
          </p>
          <div>
            <StatusBadge tone={credits.policy === 'ALLOW_DEBT' ? 'info' : 'warning'}>
              {credits.policy === 'ALLOW_DEBT'
                ? 'Capture policy: Active'
                : 'Capture policy: Enforced'}
            </StatusBadge>
          </div>
        </article>
      </section>

      {/* Control Bar: Website selector, Search, and View Switcher */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
          border: '1px solid var(--z-color-border)',
          borderRadius: 'var(--z-radius-lg)',
          background: 'var(--z-color-surface)',
          padding: '0.85rem 1.25rem',
          boxShadow: 'var(--z-shadow-card)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap', flex: 1 }}>
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              color: 'var(--z-color-ink-soft)',
              fontSize: '0.8125rem',
              fontWeight: 700,
            }}
          >
            Website
            <select
              aria-label="Website"
              value={selectedWebsiteId}
              onChange={(event) => setSelectedWebsiteId(event.target.value)}
              style={{
                minHeight: '2.35rem',
                borderRadius: 'var(--z-radius-sm)',
                border: '1px solid var(--z-color-border)',
                background: 'var(--z-color-surface-raised)',
                color: '#ffffff',
                padding: '0.35rem 0.75rem',
                fontSize: '0.8125rem',
                fontWeight: 600,
              }}
            >
              {websites.map((website) => (
                <option key={website.id} value={website.id}>
                  {website.display_name} ({website.status})
                </option>
              ))}
            </select>
          </label>

          <div
            style={{
              position: 'relative',
              display: 'flex',
              alignItems: 'center',
              minWidth: '14rem',
              flex: '1 1 14rem',
              maxWidth: '22rem',
            }}
          >
            <Search
              size={14}
              style={{
                position: 'absolute',
                left: '0.75rem',
                color: 'var(--z-color-ink-muted)',
                pointerEvents: 'none',
              }}
            />
            <input
              placeholder="Search enquiries, names, emails..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                minHeight: '2.35rem',
                paddingLeft: '2.2rem',
                paddingRight: '0.75rem',
                borderRadius: 'var(--z-radius-sm)',
                border: '1px solid var(--z-color-border)',
                background: 'var(--z-color-surface-raised)',
                color: '#ffffff',
                fontSize: '0.8125rem',
              }}
            />
          </div>
        </div>

        {/* Board / List switcher */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            background: 'var(--z-color-surface-raised)',
            borderRadius: 'var(--z-radius-md)',
            border: '1px solid var(--z-color-border)',
            padding: '0.2rem',
          }}
        >
          <button
            type="button"
            onClick={() => setViewMode('board')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.35rem 0.65rem',
              borderRadius: 'var(--z-radius-sm)',
              border: 0,
              background: viewMode === 'board' ? 'var(--z-color-surface-subtle)' : 'transparent',
              color: viewMode === 'board' ? 'var(--z-color-brand)' : 'var(--z-color-ink-muted)',
              fontSize: '0.75rem',
              fontWeight: 750,
              cursor: 'pointer',
            }}
          >
            <Kanban size={14} /> Cards
          </button>
          <button
            type="button"
            onClick={() => setViewMode('list')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.35rem 0.65rem',
              borderRadius: 'var(--z-radius-sm)',
              border: 0,
              background: viewMode === 'list' ? 'var(--z-color-surface-subtle)' : 'transparent',
              color: viewMode === 'list' ? 'var(--z-color-brand)' : 'var(--z-color-ink-muted)',
              fontSize: '0.75rem',
              fontWeight: 750,
              cursor: 'pointer',
            }}
          >
            <List size={14} /> List
          </button>
        </div>
      </div>

      {/* Leads Content */}
      {leads.length === 0 ? (
        <Notice title="No captured Leads yet">
          Zylora records valid form submissions here. It does not fabricate activity.
        </Notice>
      ) : viewMode === 'board' ? (
        /* CARDS GRID */
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(22rem, 1fr))',
            gap: '1.25rem',
          }}
        >
          {filteredLeads.map((lead) => (
            <article
              key={lead.id}
              style={{
                border: '1px solid var(--z-color-border)',
                borderRadius: 'var(--z-radius-lg)',
                background: 'var(--z-color-surface)',
                padding: '1.35rem',
                display: 'grid',
                gap: '1rem',
                boxShadow: 'var(--z-shadow-card)',
                transition: 'all var(--z-motion-fast) var(--z-ease-standard)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.85rem' }}>
                <div
                  style={{
                    width: '2.5rem',
                    height: '2.5rem',
                    borderRadius: 'var(--z-radius-md)',
                    background: 'var(--z-color-brand-soft)',
                    border: '1px solid rgba(212, 255, 50, 0.2)',
                    color: 'var(--z-color-brand)',
                    display: 'grid',
                    placeItems: 'center',
                    fontWeight: 800,
                    fontSize: '0.95rem',
                    flexShrink: 0,
                  }}
                >
                  {(lead.name || 'L').slice(0, 1).toUpperCase()}
                </div>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '0.5rem',
                    }}
                  >
                    <h3
                      style={{
                        margin: 0,
                        fontSize: '1rem',
                        fontWeight: 700,
                        color: '#ffffff',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {lead.name}
                    </h3>
                    <StatusBadge tone="success">Form Lead</StatusBadge>
                  </div>
                  {lead.email && (
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                        fontSize: '0.75rem',
                        color: 'var(--z-color-ink-muted)',
                        marginTop: '0.25rem',
                      }}
                    >
                      <Mail size={12} />
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {lead.email}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              <p
                style={{
                  margin: 0,
                  fontSize: '0.8125rem',
                  color: 'var(--z-color-ink-soft)',
                  lineHeight: 1.6,
                  background: 'rgba(0, 0, 0, 0.2)',
                  padding: '0.75rem 0.85rem',
                  borderRadius: 'var(--z-radius-sm)',
                  border: '1px solid rgba(255, 255, 255, 0.04)',
                }}
              >
                {lead.enquiry}
              </p>

              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '0.75rem',
                  color: 'var(--z-color-ink-muted)',
                  borderTop: '1px solid var(--z-color-border)',
                  paddingTop: '0.75rem',
                }}
              >
                <span>{lead.page_path || 'Direct form'}</span>
                <time dateTime={lead.captured_at}>
                  {new Date(lead.captured_at).toLocaleDateString()}
                </time>
              </div>
            </article>
          ))}
        </div>
      ) : (
        /* LIST VIEW */
        <div className="leads-panel__list" aria-live="polite">
          {filteredLeads.map((lead) => (
            <article key={lead.id} className="leads-panel__row">
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="leads-panel__heading">
                  <h2>{lead.name}</h2>
                  <StatusBadge tone="info">{lead.source}</StatusBadge>
                </div>
                <p>{lead.enquiry}</p>
                <small>
                  {[lead.email, lead.phone, lead.page_path].filter(Boolean).join(' · ')}
                </small>
              </div>
              <time dateTime={lead.captured_at}>{new Date(lead.captured_at).toLocaleString()}</time>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
