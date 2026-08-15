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
  return (
    <div className="analytics-panel">
      <section className="analytics-panel__summary" aria-label="Measured Website outcomes">
        <div>
          <p className="workspace-kicker">Last 30 days</p>
          <h2>
            {zeroLead ? 'Traffic is arriving. Let’s turn it into enquiries.' : 'Website outcomes'}
          </h2>
          <p>
            {trend(dashboard.page_view_change_percent)} · First enquiry{' '}
            {formatDate(dashboard.first_lead_at)}
          </p>
        </div>
        <StatusBadge tone={zeroLead ? 'info' : 'success'}>
          {zeroLead ? 'Opportunity detected' : 'Delivering value'}
        </StatusBadge>
      </section>

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
