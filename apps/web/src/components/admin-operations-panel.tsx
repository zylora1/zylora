'use client';

import { FormEvent, useEffect, useState } from 'react';
import { Notice, StatusBadge } from '@zylora/ui';

import { apiRequest, csrfToken } from '@/lib/api';
import { ContentOperations } from './content-operations';
import type { PortalSection } from './portal-navigation';

type Metric = { key: string; label: string; value: number };
type Overview = {
  generated_at: string;
  metrics: Metric[];
  analytics_window_start: string;
  page_views_last_30_days: number;
  leads_last_30_days: number;
};
type Growth = {
  range_days: number | null;
  funnel: Array<{ key: string; label: string; count: number; conversion_percent: number | null }>;
  active_value_sites_30d: number;
  previous_active_value_sites_30d: number;
  active_value_sites_change_percent: number | null;
  retention: Array<{
    days: number;
    eligible_accounts: number;
    retained_accounts: number;
    retention_percent: number;
  }>;
  published_with_first_lead: number;
  published_with_zero_leads: number;
  paid_with_first_lead: number;
  paid_with_zero_leads: number;
  subscription_state_counts: Record<string, number>;
};

type RecordItem = {
  id: string;
  label: string;
  detail?: string | null;
  status?: string | null;
  occurred_at?: string | null;
  attributes: Record<string, string | number | boolean | null>;
};
type UserSummary = {
  id: string;
  email: string;
  status: string;
  signup_methods: string[];
  verified_at: string | null;
  created_at: string;
  website_count: number;
  draft_count: number;
  live_website_id: string | null;
  live_website_name: string | null;
  plan_code: string | null;
  subscription_state: string | null;
};
type UserDetail = UserSummary & {
  websites: RecordItem[];
  subscriptions: RecordItem[];
  payments: RecordItem[];
  credit_ledger: RecordItem[];
  leads: RecordItem[];
  domains: RecordItem[];
  audit_activity: RecordItem[];
};

type OperationResponse = { section: string; items: RecordItem[] };
type HealthResponse = {
  status: 'ready' | 'degraded' | 'not_ready';
  checks: Record<string, string>;
};

function formatTime(value: string | null | undefined) {
  return value
    ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(
        new Date(value),
      )
    : '—';
}

function attributes(item: RecordItem) {
  return Object.entries(item.attributes)
    .filter(([, value]) => value !== null)
    .map(([key, value]) => `${key.replaceAll('_', ' ')}: ${String(value)}`)
    .join(' · ');
}

function RecordTable({ items }: { items: RecordItem[] }) {
  if (!items.length) {
    return (
      <p className="admin-operations__empty">No recorded operational state is available yet.</p>
    );
  }
  return (
    <div className="admin-operations__table-wrap">
      <table>
        <thead>
          <tr>
            <th scope="col">Record</th>
            <th scope="col">State</th>
            <th scope="col">Evidence</th>
            <th scope="col">Observed</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{item.label}</strong>
                {item.detail ? <span>{item.detail}</span> : null}
              </td>
              <td>
                {item.status ? (
                  <StatusBadge
                    tone={
                      item.status === 'ACTIVE' || item.status === 'ready' ? 'success' : 'neutral'
                    }
                  >
                    {item.status}
                  </StatusBadge>
                ) : (
                  '—'
                )}
              </td>
              <td>{attributes(item) || '—'}</td>
              <td>{formatTime(item.occurred_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AdminOverviewPanel() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [growth, setGrowth] = useState<Growth | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!csrfToken('zylora_admin_csrf')) return;
    void Promise.all([
      apiRequest<Overview>('/api/v1/admin/overview'),
      apiRequest<Growth>('/api/v1/admin/analytics/growth?period_days=30'),
    ])
      .then(([nextOverview, nextGrowth]) => {
        setOverview(nextOverview);
        setGrowth(nextGrowth);
      })
      .catch((reason: unknown) =>
        setError(reason instanceof Error ? reason.message : 'Overview is unavailable.'),
      );
  }, []);
  if (error)
    return (
      <Notice tone="danger" title="Operational overview unavailable">
        {error}
      </Notice>
    );
  if (!overview || !growth) return <p role="status">Loading measured operational state…</p>;
  return (
    <div className="admin-operations">
      <section className="admin-operations__summary" aria-label="Measured platform summary">
        <div>
          <p className="workspace-kicker">Measured platform state</p>
          <h2>Authoritative operations</h2>
          <p>
            Generated {formatTime(overview.generated_at)} from PostgreSQL records and analytics
            rollups.
          </p>
        </div>
        <StatusBadge tone="info">No synthetic metrics</StatusBadge>
      </section>
      <section className="admin-operations__north-star" aria-labelledby="north-star-title">
        <div>
          <p className="workspace-kicker">North Star · last 30 days</p>
          <h2 id="north-star-title">Published Websites delivering real enquiries</h2>
        </div>
        <strong>{growth.active_value_sites_30d}</strong>
        <span>
          {growth.active_value_sites_change_percent === null
            ? 'No comparable prior period'
            : `${growth.active_value_sites_change_percent > 0 ? '+' : ''}${growth.active_value_sites_change_percent}% vs prior 30 days`}
        </span>
      </section>
      <section className="admin-operations__funnel" aria-labelledby="growth-funnel-title">
        <p className="workspace-kicker">30-day product funnel</p>
        <h2 id="growth-funnel-title">From account to demonstrated value</h2>
        <ol>
          {growth.funnel.map((step) => (
            <li key={step.key}>
              <span>{step.label}</span>
              <strong>{step.count}</strong>
              <small>
                {step.conversion_percent === null
                  ? '—'
                  : `${step.conversion_percent}% from prior step`}
              </small>
            </li>
          ))}
        </ol>
      </section>
      <dl className="admin-operations__metrics" aria-label="Published and paid value segments">
        <div>
          <dt>Published + first lead</dt>
          <dd>{growth.published_with_first_lead}</dd>
        </div>
        <div>
          <dt>Published + zero leads</dt>
          <dd>{growth.published_with_zero_leads}</dd>
        </div>
        <div>
          <dt>Paid + first lead</dt>
          <dd>{growth.paid_with_first_lead}</dd>
        </div>
        <div>
          <dt>Paid + zero leads</dt>
          <dd>{growth.paid_with_zero_leads}</dd>
        </div>
      </dl>
      <section className="admin-operations__retention" aria-labelledby="retention-title">
        <div>
          <p className="workspace-kicker">Account retention</p>
          <h2 id="retention-title">Verified 30, 60 and 90-day cohorts</h2>
        </div>
        <dl>
          {growth.retention.map((cohort) => (
            <div key={cohort.days}>
              <dt>{cohort.days} days</dt>
              <dd>{cohort.retention_percent}%</dd>
              <small>
                {cohort.retained_accounts} of {cohort.eligible_accounts} eligible accounts
              </small>
            </div>
          ))}
        </dl>
        <p>
          Subscriptions: {growth.subscription_state_counts.ACTIVE ?? 0} active ·{' '}
          {growth.subscription_state_counts.PAST_DUE ?? 0} payment-failed/past due ·{' '}
          {growth.subscription_state_counts.CANCELLED ?? 0} cancelled ·{' '}
          {growth.subscription_state_counts.EXPIRED ?? 0} expired ·{' '}
          {growth.subscription_state_counts.FAILED ?? 0} failed setup
        </p>
      </section>
      <dl className="admin-operations__metrics">
        {overview.metrics.map((metric) => (
          <div key={metric.key}>
            <dt>{metric.label}</dt>
            <dd>{metric.value}</dd>
          </div>
        ))}
      </dl>
      <p className="admin-operations__footnote">
        Last 30 measured days since {overview.analytics_window_start}:{' '}
        {overview.page_views_last_30_days} page views and {overview.leads_last_30_days} Leads.
      </p>
    </div>
  );
}

function AdminUsersPanel() {
  const [query, setQuery] = useState('');
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [detail, setDetail] = useState<UserDetail | null>(null);
  const [error, setError] = useState('');
  const load = async (nextQuery = '') => {
    try {
      const response = await apiRequest<{ items: UserSummary[] }>(
        `/api/v1/admin/users?query=${encodeURIComponent(nextQuery)}`,
      );
      setUsers(response.items);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'User search is unavailable.');
    }
  };
  useEffect(() => {
    if (csrfToken('zylora_admin_csrf')) void Promise.resolve().then(() => load());
  }, []);
  const search = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void load(query);
  };
  const view = async (userId: string) => {
    try {
      setDetail(await apiRequest<UserDetail>(`/api/v1/admin/users/${userId}`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'User record is unavailable.');
    }
  };
  return (
    <div className="admin-operations">
      {error ? (
        <Notice tone="danger" title="User operations unavailable">
          {error}
        </Notice>
      ) : null}
      <form className="admin-operations__search" onSubmit={search}>
        <label htmlFor="admin-user-search">Search email</label>
        <input
          id="admin-user-search"
          value={query}
          maxLength={160}
          onChange={(event) => setQuery(event.target.value)}
        />
        <button type="submit">Search</button>
      </form>
      <div className="admin-operations__user-grid">
        <section aria-label="User search results">
          {!users.length ? (
            <p className="admin-operations__empty">No User records match this search.</p>
          ) : (
            users.map((user) => (
              <button
                className="admin-operations__user"
                type="button"
                key={user.id}
                onClick={() => void view(user.id)}
              >
                <strong>{user.email}</strong>
                <span>
                  {user.status} · {user.signup_methods.join(', ') || 'No recorded method'}
                </span>
                <small>
                  {user.website_count} Websites · {user.draft_count} Drafts ·{' '}
                  {user.plan_code ?? 'FREE'}
                </small>
              </button>
            ))
          )}
        </section>
        <section aria-live="polite">
          {detail ? (
            <UserDetailPanel detail={detail} />
          ) : (
            <p className="admin-operations__empty">
              Select a User to view verified account, commercial, credit, Lead, domain, and audit
              state.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}

function UserDetailPanel({ detail }: { detail: UserDetail }) {
  const [error, setError] = useState('');
  const adjust = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const token = csrfToken('zylora_admin_csrf');
    try {
      await apiRequest(`/api/v1/admin/users/${detail.id}/lead-credits`, {
        method: 'POST',
        headers: { 'X-CSRF-Token': token ?? '', 'Idempotency-Key': crypto.randomUUID() },
        body: JSON.stringify({ delta: Number(data.get('delta')), reason: data.get('reason') }),
      });
      event.currentTarget.reset();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Lead-credit adjustment failed.');
    }
  };
  return (
    <div className="admin-operations__detail">
      <h2>{detail.email}</h2>
      <p>
        {detail.status} · {detail.verified_at ? 'Verified' : 'Not verified'} ·{' '}
        {detail.live_website_name ?? 'No live Website'}
      </p>
      {error ? (
        <Notice tone="danger" title="Credit adjustment failed">
          {error}
        </Notice>
      ) : null}
      <form className="admin-operations__credit" onSubmit={adjust}>
        <label>
          Lead-credit adjustment
          <input name="delta" required type="number" min="-1000000" max="1000000" />
        </label>
        <label>
          Reason
          <input name="reason" required minLength={1} maxLength={240} />
        </label>
        <button type="submit">Record adjustment</button>
      </form>
      {(
        [
          ['Websites', detail.websites],
          ['Subscriptions and invoices', detail.subscriptions],
          ['Payments', detail.payments],
          ['Credits', detail.credit_ledger],
          ['Leads', detail.leads],
          ['Domains', detail.domains],
          ['Audit activity', detail.audit_activity],
        ] as const
      ).map(([title, items]) => (
        <section key={title}>
          <h3>{title}</h3>
          <RecordTable items={items} />
        </section>
      ))}
    </div>
  );
}

function AdminHealthPanel() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!csrfToken('zylora_admin_csrf')) return;
    void apiRequest<HealthResponse>('/api/v1/admin/health')
      .then(setHealth)
      .catch((reason: unknown) =>
        setError(reason instanceof Error ? reason.message : 'Health checks are unavailable.'),
      );
  }, []);
  if (error)
    return (
      <Notice tone="danger" title="Health checks unavailable">
        {error}
      </Notice>
    );
  if (!health) return <p role="status">Checking live operational dependencies…</p>;
  return (
    <div className="admin-operations">
      <section className="admin-operations__summary">
        <div>
          <p className="workspace-kicker">Observed now</p>
          <h2>System health</h2>
          <p>These values are live probe outcomes, not a static service badge.</p>
        </div>
        <StatusBadge
          tone={
            health.status === 'ready'
              ? 'success'
              : health.status === 'degraded'
                ? 'warning'
                : 'danger'
          }
        >
          {health.status}
        </StatusBadge>
      </section>
      <dl className="admin-operations__checks">
        {Object.entries(health.checks).map(([key, value]) => (
          <div key={key}>
            <dt>{key}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function AdminConfigurationPanel() {
  const [items, setItems] = useState<RecordItem[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const load = async () => {
    try {
      setItems(
        (await apiRequest<OperationResponse>('/api/v1/admin/operations/configuration')).items,
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Configuration is unavailable.');
    }
  };
  useEffect(() => {
    if (csrfToken('zylora_admin_csrf')) void Promise.resolve().then(() => load());
  }, []);
  const configure = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const token = csrfToken('zylora_admin_csrf');
    try {
      await apiRequest('/api/v1/admin/export-prices', {
        method: 'POST',
        headers: { 'X-CSRF-Token': token ?? '' },
        body: JSON.stringify({
          currency: data.get('currency'),
          amount_minor: Number(data.get('amount_minor')),
          active: true,
        }),
      });
      setNotice('A versioned ZIP export price was recorded.');
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'ZIP export price update failed.');
    }
  };
  return (
    <div className="admin-operations">
      {error ? (
        <Notice tone="danger" title="Configuration unavailable">
          {error}
        </Notice>
      ) : null}
      {notice ? (
        <Notice tone="success" title="Configuration updated">
          {notice}
        </Notice>
      ) : null}
      <form className="admin-operations__search" onSubmit={configure}>
        <label>
          ZIP export currency
          <select name="currency" defaultValue="INR">
            <option>INR</option>
            <option>USD</option>
          </select>
        </label>
        <label>
          Minor-unit amount
          <input name="amount_minor" type="number" min="1" required />
        </label>
        <button type="submit">Add versioned ZIP price</button>
      </form>
      <RecordTable items={items} />
    </div>
  );
}

function AdminOperationalRecords({ section }: { section: PortalSection }) {
  const [items, setItems] = useState<RecordItem[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!csrfToken('zylora_admin_csrf')) return;
    void apiRequest<OperationResponse>(`/api/v1/admin/operations/${section.slug}`)
      .then((response) => setItems(response.items))
      .catch((reason: unknown) =>
        setError(reason instanceof Error ? reason.message : `${section.label} is unavailable.`),
      );
  }, [section.label, section.slug]);

  if (error)
    return (
      <Notice tone="danger" title={`${section.label} unavailable`}>
        {error}
      </Notice>
    );
  return (
    <div className="admin-operations">
      <RecordTable items={items} />
    </div>
  );
}

export function AdminSectionPanel({ section }: { section: PortalSection }) {
  if (section.slug === 'users') return <AdminUsersPanel />;
  if (section.slug === 'health') return <AdminHealthPanel />;
  if (section.slug === 'configuration') return <AdminConfigurationPanel />;
  if (section.slug === 'communications') return <ContentOperations />;
  return <AdminOperationalRecords section={section} />;
}
