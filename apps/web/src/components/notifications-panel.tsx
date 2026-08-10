'use client';

import { Notice, StatusBadge } from '@zylora/ui';
import { useEffect, useState } from 'react';

import { apiRequest, csrfToken } from '@/lib/api';

type Notification = {
  id: string;
  title: string;
  body: string;
  href: string;
  state: 'UNREAD' | 'READ';
  created_at: string;
};

type NotificationPage = {
  notifications: Notification[];
  unread_count: number;
  next_cursor: string | null;
};

export function NotificationsPanel() {
  const [page, setPage] = useState<NotificationPage | null>(null);
  const [error, setError] = useState('');
  const [updatingId, setUpdatingId] = useState('');

  useEffect(() => {
    if (!csrfToken('zylora_user_csrf')) return;
    let active = true;
    void apiRequest<NotificationPage>('/api/v1/notifications?limit=30')
      .then((result) => {
        if (active) setPage(result);
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : 'Notifications are unavailable.');
        }
      });
    return () => {
      active = false;
    };
  }, []);

  async function markRead(notification: Notification) {
    if (notification.state === 'READ') return;
    setUpdatingId(notification.id);
    try {
      const csrf = csrfToken('zylora_user_csrf');
      const updated = await apiRequest<Notification>(
        `/api/v1/notifications/${notification.id}/read`,
        {
          method: 'POST',
          body: '{}',
          headers: csrf ? { 'X-CSRF-Token': csrf } : {},
        },
      );
      setPage((current) =>
        current
          ? {
              ...current,
              unread_count: Math.max(0, current.unread_count - 1),
              notifications: current.notifications.map((item) =>
                item.id === updated.id ? updated : item,
              ),
            }
          : current,
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Notification update failed.');
    } finally {
      setUpdatingId('');
    }
  }

  async function loadOlder() {
    if (!page?.next_cursor) return;
    try {
      const older = await apiRequest<NotificationPage>(
        `/api/v1/notifications?limit=30&before=${encodeURIComponent(page.next_cursor)}`,
      );
      setPage((current) =>
        current
          ? {
              ...older,
              notifications: [...current.notifications, ...older.notifications],
              unread_count: older.unread_count,
            }
          : older,
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Notifications are unavailable.');
    }
  }

  if (error) {
    return (
      <Notice tone="danger" title="Notifications unavailable">
        {error}
      </Notice>
    );
  }
  if (!page) {
    return (
      <Notice title="You are all caught up">
        Important Website, Lead, billing, domain, transfer, and export updates will appear here.
      </Notice>
    );
  }
  if (!page) return <p role="status">Loading notifications…</p>;
  if (page.notifications.length === 0) {
    return (
      <Notice title="You are all caught up">
        Important Website, Lead, billing, domain, transfer, and export updates will appear here.
      </Notice>
    );
  }
  return (
    <div className="notifications-panel">
      <section className="notifications-panel__summary" aria-label="Notification summary">
        <div>
          <p className="workspace-kicker">Account updates</p>
          <h2>Notifications</h2>
        </div>
        <StatusBadge tone={page.unread_count > 0 ? 'info' : 'success'}>
          {page.unread_count} unread
        </StatusBadge>
      </section>
      <div className="notifications-panel__list" aria-live="polite">
        {page.notifications.map((notification) => (
          <article
            className={
              notification.state === 'UNREAD'
                ? 'notifications-panel__row notifications-panel__row--unread'
                : 'notifications-panel__row'
            }
            key={notification.id}
          >
            <div>
              <div className="notifications-panel__heading">
                <h3>{notification.title}</h3>
                <StatusBadge tone={notification.state === 'UNREAD' ? 'info' : 'neutral'}>
                  {notification.state === 'UNREAD' ? 'Unread' : 'Read'}
                </StatusBadge>
              </div>
              <p>{notification.body}</p>
              <time dateTime={notification.created_at}>
                {new Date(notification.created_at).toLocaleString()}
              </time>
            </div>
            <div className="notifications-panel__actions">
              <a href={notification.href}>Open</a>
              {notification.state === 'UNREAD' ? (
                <button
                  disabled={updatingId === notification.id}
                  type="button"
                  onClick={() => void markRead(notification)}
                >
                  Mark as read
                </button>
              ) : null}
            </div>
          </article>
        ))}
      </div>
      {page.next_cursor ? (
        <button
          className="notifications-panel__more"
          type="button"
          onClick={() => void loadOlder()}
        >
          Load older notifications
        </button>
      ) : null}
    </div>
  );
}
