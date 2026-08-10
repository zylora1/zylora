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
  form_leads: number;
  chatbot_leads: number;
  chatbot_conversations: number;
  chatbot_messages: number;
  conversions: number;
  points: AnalyticsPoint[];
};

const metricLabels: Array<
  [
    keyof Pick<
      AnalyticsDashboard,
      | 'page_views'
      | 'sessions'
      | 'visitors'
      | 'leads'
      | 'form_leads'
      | 'chatbot_leads'
      | 'chatbot_conversations'
    >,
    string,
  ]
> = [
  ['page_views', 'Page views'],
  ['sessions', 'Sessions'],
  ['visitors', 'Visitors'],
  ['leads', 'Leads'],
  ['form_leads', 'Form leads'],
  ['chatbot_leads', 'Chatbot leads'],
  ['chatbot_conversations', 'Chatbot conversations'],
];

export function AnalyticsPanel() {
  const [dashboard, setDashboard] = useState<AnalyticsDashboard | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!csrfToken('zylora_user_csrf')) return;
    let active = true;
    void apiRequest<AnalyticsDashboard>('/api/v1/analytics?period_days=30')
      .then((result) => {
        if (active) setDashboard(result);
      })
      .catch((reason: unknown) => {
        if (active)
          setError(reason instanceof Error ? reason.message : 'Analytics are unavailable.');
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
  if (!dashboard) {
    return (
      <EmptyState
        eyebrow="Current state"
        title="Analytics begins with real traffic"
        description="There are no charts or zero-value metrics to show before a Website is published and receives activity."
      />
    );
  }
  if (!dashboard) return <p role="status">Loading verified analytics…</p>;
  if (!dashboard.has_published_website) {
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
      <Notice title="No analytics yet">
        Your Website is published, but it has not received measurable visitor, Lead, or chatbot
        activity in this period. Zylora does not invent charts or zero-value metrics.
      </Notice>
    );
  }
  return (
    <div className="analytics-panel">
      <section className="analytics-panel__summary" aria-label="Measured Website activity">
        <div>
          <p className="workspace-kicker">Last 30 days</p>
          <h2>Measured Website activity</h2>
          <p>Only recorded activity appears here. Metrics are refreshed in the account timezone.</p>
        </div>
        <StatusBadge tone="success">Verified rollups</StatusBadge>
      </section>
      <dl className="analytics-panel__metrics">
        {metricLabels.map(([key, label]) => (
          <div key={key}>
            <dt>{label}</dt>
            <dd>{dashboard[key]}</dd>
          </div>
        ))}
      </dl>
      <section className="analytics-panel__daily" aria-labelledby="analytics-daily-title">
        <div>
          <p className="workspace-kicker">Daily activity</p>
          <h2 id="analytics-daily-title">Recorded days</h2>
        </div>
        <div className="analytics-panel__table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Views</th>
                <th scope="col">Sessions</th>
                <th scope="col">Leads</th>
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
                  <td>{point.page_views}</td>
                  <td>{point.sessions}</td>
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
