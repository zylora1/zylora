'use client';

import { useEffect, useState } from 'react';
import { Notice, StatusBadge } from '@zylora/ui';

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
    <div className="leads-panel">
      <section className="leads-panel__summary" aria-label="Lead credit status">
        <div>
          <p className="workspace-kicker">Lead credits</p>
          <strong>{credits.balance}</strong>
          <span>Current ledger balance</span>
        </div>
        <StatusBadge tone={credits.policy === 'ALLOW_DEBT' ? 'info' : 'warning'}>
          {credits.policy === 'ALLOW_DEBT'
            ? 'Capture remains available'
            : 'Capture policy enforced'}
        </StatusBadge>
      </section>
      <label className="leads-panel__selector">
        <span>Website</span>
        <select
          value={selectedWebsiteId}
          onChange={(event) => setSelectedWebsiteId(event.target.value)}
        >
          {websites.map((website) => (
            <option key={website.id} value={website.id}>
              {website.display_name} — {website.status}
            </option>
          ))}
        </select>
      </label>
      {leads.length === 0 ? (
        <Notice title="No captured Leads yet">
          Zylora records valid form and chatbot submissions here. It does not fabricate activity.
        </Notice>
      ) : (
        <div className="leads-panel__list" aria-live="polite">
          {leads.map((lead) => (
            <article key={lead.id} className="leads-panel__row">
              <div>
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
