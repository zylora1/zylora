'use client';

import { ActionLink, EmptyState, Notice, StatusBadge } from '@zylora/ui';
import { useEffect, useState } from 'react';

import { apiRequest, csrfToken } from '@/lib/api';

type AnalyticsPoint = {
  date: string;
  page_views: number;
  sessions: number;
  visitors: number;
  leads: number;
  lead_form_opens: number;
  lead_form_submissions: number;
  form_leads: number;
  chatbot_leads: number;
  chatbot_conversations: number;
  chatbot_messages: number;
  conversions: number;
};

type AnalyticsDashboard = {
  has_published_website: boolean;
  has_meaningful_data: boolean;
  page_views: number;
  sessions: number;
  visitors: number;
  leads: number;
  lead_form_opens: number;
  lead_form_submissions: number;
  form_leads: number;
  chatbot_conversations: number;
  chatbot_messages: number;
  lead_conversion_rate: number;
  published_at: string | null;
  first_visitor_at: string | null;
  first_lead_at: string | null;
  time_to_first_lead_seconds: number | null;
  previous_page_views: number;
  previous_leads: number;
  page_view_change_percent: number | null;
  lead_change_percent: number | null;
  zero_lead_recommendations: string[];
  points: AnalyticsPoint[];
};

function formatDate(value: string | null): string {
  return value
    ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value))
    : 'Not yet';
}

function trend(value: number | null): string {
  if (value === null) return 'No comparable prior period';
  return `${value > 0 ? '+' : ''}${value}% vs previous 30 days`;
}

const outcomeMetrics: Array<[keyof AnalyticsDashboard, string]> = [
  ['visitors', 'Visitors'],
  ['leads', 'Enquiries'],
  ['lead_conversion_rate', 'Visitor → enquiry'],
  ['chatbot_conversations', 'Chatbot conversations'],
  ['lead_form_opens', 'Enquiry form opens'],
];

export function AnalyticsPanel() {
  const [dashboard, setDashboard] = useState<AnalyticsDashboard | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!csrfToken('zylora_user_csrf')) {
      void Promise.resolve().then(() => setLoading(false));
      return;
    }
    let active = true;
    void apiRequest<AnalyticsDashboard>('/api/v1/analytics?period_days=30')
      .then((result) => {
        if (active) setDashboard(result);
      })
      .catch((reason: unknown) => {
        if (active)
          setError(reason instanceof Error ? reason.message : 'Analytics are unavailable.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  if (error) {
    return (
      <Notice tone="danger" title="Analytics unavailable">
        {error}
      </Notice>
    );
  }
  if (loading) return <p role="status">Loading verified analytics…</p>;
  if (!dashboard?.has_published_website) {
    return (
      <EmptyState
        eyebrow="First Website"
        title="Publish your first website"
        description="Analytics becomes available after your published Website receives real activity."
        action={<ActionLink href="/app/templates">Choose a Template</ActionLink>}
      />
    );
  }
  if (!dashboard.has_meaningful_data) {
    return (
      <EmptyState
        eyebrow="Website live"
        title="Your Website is ready for its first visitor"
        description="Share the published link. Zylora will show measured traffic, enquiries, and chatbot usage here—never synthetic data."
        action={<ActionLink href="/app/websites">Open Website management</ActionLink>}
      />
    );
  }

  const zeroLead = dashboard.leads === 0;
  const maxVisitors = Math.max(...dashboard.points.map((p) => p.visitors || p.sessions || 1), 1);

  return (
    <div className="analytics-panel" style={{ display: 'grid', gap: '1.75rem' }}>
      {/* Summary Focal Header */}
      <section
        className="analytics-panel__summary"
        aria-label="Measured Website outcomes"
        style={{
          border: '1px solid var(--z-color-border)',
          borderRadius: 'var(--z-radius-lg)',
          background: 'var(--z-color-surface)',
          padding: '1.5rem',
          boxShadow: 'var(--z-shadow-card)',
        }}
      >
        <div>
          <p className="workspace-kicker">Last 30 days</p>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 600, color: '#ffffff', letterSpacing: '-0.03em' }}>
            {zeroLead ? 'Traffic is arriving. Let’s turn it into enquiries.' : 'Website outcomes'}
          </h2>
          <p style={{ margin: '0.35rem 0 0', color: 'var(--z-color-ink-muted)', fontSize: '0.8125rem' }}>
            {trend(dashboard.page_view_change_percent)} · First enquiry{' '}
            {formatDate(dashboard.first_lead_at)}
          </p>
        </div>
        <StatusBadge tone={zeroLead ? 'info' : 'success'}>
          {zeroLead ? 'Opportunity detected' : 'Delivering value'}
        </StatusBadge>
      </section>

      {/* KPI Metric Strip */}
      <dl className="analytics-panel__metrics">
        {outcomeMetrics.map(([key, label]) => (
          <div key={key}>
            <dt>{label}</dt>
            <dd>
              {key === 'lead_conversion_rate'
                ? `${dashboard.lead_conversion_rate.toFixed(2)}%`
                : String(dashboard[key])}
            </dd>
          </div>
        ))}
      </dl>

      {/* Actionable recommendations for 0 leads */}
      {zeroLead ? (
        <section className="analytics-panel__intervention" aria-labelledby="zero-lead-title">
          <p className="workspace-kicker">Practical next steps</p>
          <h2 id="zero-lead-title">
            Your Website is live, but it has not received an enquiry yet.
          </h2>
          <ol>
            {dashboard.zero_lead_recommendations.map((recommendation) => (
              <li key={recommendation}>{recommendation}</li>
            ))}
          </ol>
          <ActionLink href="/app/websites">Review your Website</ActionLink>
        </section>
      ) : null}

      {/* Visual Activity Trend Chart (Dark Embedded Surface) */}
      {dashboard.points.length > 0 && (
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
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <p className="workspace-kicker" style={{ margin: '0 0 0.25rem' }}>
                Traffic Velocity
              </p>
              <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 600, color: '#ffffff' }}>
                Visitor Activity (Last 30 Days)
              </h3>
            </div>
            <span
              style={{
                fontSize: '0.75rem',
                fontFamily: 'var(--z-font-mono)',
                color: 'var(--z-color-brand)',
                background: 'var(--z-color-surface-raised)',
                padding: '0.25rem 0.6rem',
                borderRadius: 'var(--z-radius-round)',
                border: '1px solid var(--z-color-border)',
              }}
            >
              Max: {maxVisitors} visits/day
            </span>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'flex-end',
              gap: '0.35rem',
              height: '8rem',
              padding: '0.5rem 0',
              borderBottom: '1px solid var(--z-color-border)',
            }}
          >
            {dashboard.points.map((point) => {
              const val = point.visitors || point.sessions || 0;
              const heightPct = Math.max(8, Math.round((val / maxVisitors) * 100));
              return (
                <div
                  key={point.date}
                  style={{
                    flex: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    height: '100%',
                    justifyContent: 'flex-end',
                  }}
                  title={`${point.date}: ${val} visitors, ${point.leads} enquiries`}
                >
                  <div
                    style={{
                      width: '100%',
                      maxWidth: '1.2rem',
                      height: `${heightPct}%`,
                      borderRadius: '0.2rem 0.2rem 0 0',
                      background:
                        point.leads > 0
                          ? 'var(--z-color-brand)'
                          : 'var(--z-color-surface-hover)',
                      boxShadow:
                        point.leads > 0 ? '0 0 10px rgba(212, 255, 50, 0.4)' : 'none',
                      transition: 'height 200ms ease-out',
                    }}
                  />
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Recorded Performance Table */}
      <section className="analytics-panel__daily" aria-labelledby="analytics-daily-title">
        <div>
          <p className="workspace-kicker">Performance trend</p>
          <h2 id="analytics-daily-title">Recorded days</h2>
        </div>
        <div className="analytics-panel__table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Visitors</th>
                <th scope="col">Form opens</th>
                <th scope="col">Enquiries</th>
                <th scope="col">Chatbot</th>
              </tr>
            </thead>
            <tbody>
              {dashboard.points.map((point) => (
                <tr key={point.date}>
                  <td>
                    {new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(
                      new Date(`${point.date}T00:00:00`),
                    )}
                  </td>
                  <td>{point.visitors || point.sessions}</td>
                  <td>{point.lead_form_opens}</td>
                  <td>{point.leads}</td>
                  <td>{point.chatbot_conversations}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
