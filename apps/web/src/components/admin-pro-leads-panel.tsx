'use client';

import { useCallback, useEffect, useState } from 'react';
import { Notice, StatusBadge } from '@zylora/ui';

import { apiRequest } from '@/lib/api';

type ProLead = {
  id: string;
  reference_id: string;
  name: string;
  email: string;
  website_type: string;
  preferred_contact_time: string;
  status: 'PENDING' | 'CLOSED' | 'NOT_CLOSED';
  amount_received: number | null;
  submitted_at: string;
  resolved_at: string | null;
};

type ProLeadSummary = {
  total_pro_leads: number;
  closed: number;
  not_closed: number;
  pending: number;
  amount_received: number;
};

type ProLeadListResponse = {
  items: ProLead[];
  summary: ProLeadSummary;
};

function formatTime(value: string | null | undefined) {
  return value
    ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(
        new Date(value),
      )
    : '—';
}

function formatMoney(amountMinor: number | null) {
  if (amountMinor === null || amountMinor === undefined) return '—';
  return `₹${amountMinor.toLocaleString()}`;
}

export function AdminProLeadsPanel() {
  const [data, setData] = useState<ProLeadListResponse | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [activeModalLead, setActiveModalLead] = useState<ProLead | null>(null);
  const [closedAmountInput, setClosedAmountInput] = useState('');
  const [actionError, setActionError] = useState('');
  const [actionSubmitting, setActionSubmitting] = useState(false);

  const fetchProLeads = useCallback(() => {
    void apiRequest<ProLeadListResponse>('/api/v1/admin/pro-leads')
      .then((res) => {
        setData(res);
        setError('');
      })
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : 'Pro leads are unavailable.');
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchProLeads();
  }, [fetchProLeads]);

  const markClosed = async (leadId: string, amount: number) => {
    setActionError('');
    setActionSubmitting(true);
    try {
      await apiRequest(`/api/v1/admin/pro-leads/${leadId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({
          status: 'CLOSED',
          amount_received: amount,
        }),
      });
      setActiveModalLead(null);
      setClosedAmountInput('');
      fetchProLeads();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Could not update lead status.');
    } finally {
      setActionSubmitting(false);
    }
  };

  const markNotClosed = async (leadId: string) => {
    setActionError('');
    setActionSubmitting(true);
    try {
      await apiRequest(`/api/v1/admin/pro-leads/${leadId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({
          status: 'NOT_CLOSED',
        }),
      });
      fetchProLeads();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Could not update lead status.');
    } finally {
      setActionSubmitting(false);
    }
  };

  if (loading && !data) {
    return <p className="admin-operations__loading">Loading Pro leads…</p>;
  }

  if (error && !data) {
    return (
      <Notice tone="danger" title="Pro leads unavailable">
        {error}
      </Notice>
    );
  }

  const summary = data?.summary || {
    total_pro_leads: 0,
    closed: 0,
    not_closed: 0,
    pending: 0,
    amount_received: 0,
  };

  return (
    <div className="admin-pro-leads">
      <div className="admin-overview__grid" style={{ marginBottom: '1.5rem' }}>
        <article className="admin-overview__card">
          <p className="admin-overview__label">Total Pro Leads</p>
          <p className="admin-overview__value">{summary.total_pro_leads}</p>
        </article>
        <article className="admin-overview__card">
          <p className="admin-overview__label">Closed</p>
          <p className="admin-overview__value" style={{ color: '#166534' }}>
            {summary.closed}
          </p>
        </article>
        <article className="admin-overview__card">
          <p className="admin-overview__label">Not Closed</p>
          <p className="admin-overview__value" style={{ color: '#991b1b' }}>
            {summary.not_closed}
          </p>
        </article>
        <article className="admin-overview__card">
          <p className="admin-overview__label">Pending</p>
          <p className="admin-overview__value" style={{ color: '#854d0e' }}>
            {summary.pending}
          </p>
        </article>
        <article className="admin-overview__card">
          <p className="admin-overview__label">Amount Received</p>
          <p className="admin-overview__value">₹{summary.amount_received.toLocaleString()}</p>
        </article>
      </div>

      {actionError ? (
        <Notice tone="danger" title="Action failed">
          {actionError}
        </Notice>
      ) : null}

      {!data?.items.length ? (
        <p className="admin-operations__empty">No Pro sales enquiries have been received yet.</p>
      ) : (
        <div className="admin-operations__table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Reference ID</th>
                <th scope="col">Name & Email</th>
                <th scope="col">Website Type</th>
                <th scope="col">Preferred Time</th>
                <th scope="col">Submitted</th>
                <th scope="col">Status</th>
                <th scope="col">Amount Received</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((lead) => (
                <tr key={lead.id}>
                  <td>
                    <strong>{lead.reference_id}</strong>
                  </td>
                  <td>
                    <strong>{lead.name}</strong>
                    <br />
                    <small>{lead.email}</small>
                  </td>
                  <td>{lead.website_type}</td>
                  <td>{lead.preferred_contact_time}</td>
                  <td>{formatTime(lead.submitted_at)}</td>
                  <td>
                    <StatusBadge
                      tone={
                        lead.status === 'CLOSED'
                          ? 'success'
                          : lead.status === 'NOT_CLOSED'
                            ? 'neutral'
                            : 'warning'
                      }
                    >
                      {lead.status === 'CLOSED'
                        ? 'Closed'
                        : lead.status === 'NOT_CLOSED'
                          ? 'Not Closed'
                          : 'Pending'}
                    </StatusBadge>
                  </td>
                  <td>{formatMoney(lead.amount_received)}</td>
                  <td>
                    {lead.status === 'PENDING' ? (
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button
                          type="button"
                          className="button button--small button--secondary"
                          onClick={() => {
                            setActiveModalLead(lead);
                            setClosedAmountInput('');
                            setActionError('');
                          }}
                        >
                          Mark Closed
                        </button>
                        <button
                          type="button"
                          className="button button--small button--ghost"
                          onClick={() => markNotClosed(lead.id)}
                          disabled={actionSubmitting}
                        >
                          Not Closed
                        </button>
                      </div>
                    ) : (
                      <small style={{ color: '#6b7280' }}>
                        Resolved {formatTime(lead.resolved_at)}
                      </small>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {activeModalLead ? (
        <div
          className="modal-backdrop"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
          }}
        >
          <div
            className="modal-content"
            style={{
              background: '#fff',
              padding: '1.5rem',
              borderRadius: '0.75rem',
              maxWidth: '400px',
              width: '100%',
            }}
          >
            <h3>Mark lead as Closed</h3>
            <p>
              Enter the actual amount received for lead{' '}
              <strong>{activeModalLead.reference_id}</strong> ({activeModalLead.name}).
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const amount = parseInt(closedAmountInput, 10);
                if (isNaN(amount) || amount < 0) {
                  setActionError('Please enter a valid positive amount.');
                  return;
                }
                markClosed(activeModalLead.id, amount);
              }}
            >
              <label style={{ display: 'block', margin: '1rem 0' }}>
                Amount received (₹)
                <input
                  type="number"
                  min="0"
                  required
                  value={closedAmountInput}
                  onChange={(e) => setClosedAmountInput(e.target.value)}
                  placeholder="e.g. 25000"
                  style={{ width: '100%', padding: '0.5rem', marginTop: '0.25rem' }}
                />
              </label>
              <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  onClick={() => setActiveModalLead(null)}
                  disabled={actionSubmitting}
                >
                  Cancel
                </button>
                <button type="submit" disabled={actionSubmitting}>
                  {actionSubmitting ? 'Confirming…' : 'Confirm Closed'}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
