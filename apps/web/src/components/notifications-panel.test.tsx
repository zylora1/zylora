import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { NotificationsPanel } from './notifications-panel';

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = 'zylora_user_csrf=; Max-Age=0';
});

const firstNotification = {
  id: 'notice-1',
  title: 'New lead captured',
  body: 'A form enquiry is ready to review.',
  href: '/app/leads',
  state: 'UNREAD',
  created_at: '2026-08-10T09:00:00Z',
};

describe('Phase 11 Notifications panel', () => {
  it('shows durable notifications, marks only the requested item as read, and loads another page', async () => {
    document.cookie = 'zylora_user_csrf=notifications-test';
    const fetcher = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/notifications?limit=30') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            notifications: [firstNotification],
            unread_count: 1,
            next_cursor: '2026-08-10T08:00:00Z',
          }),
        });
      }
      if (path === '/api/v1/notifications/notice-1/read') {
        expect(init?.method).toBe('POST');
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            ...firstNotification,
            state: 'READ',
            read_at: '2026-08-10T09:01:00Z',
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({
          notifications: [
            {
              id: 'notice-older',
              title: 'Website published',
              body: 'Your Website is live.',
              href: '/app/websites',
              state: 'READ',
              created_at: '2026-08-09T09:00:00Z',
            },
          ],
          unread_count: 0,
          next_cursor: null,
        }),
      });
    });
    vi.stubGlobal('fetch', fetcher);
    render(<NotificationsPanel />);

    expect(await screen.findByText('New lead captured')).toBeVisible();
    expect(screen.getByText('1 unread')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Mark as read' }));
    expect(await screen.findByText('0 unread')).toBeVisible();
    expect(screen.getByText('Read')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Load older notifications' }));
    expect(await screen.findByText('Website published')).toBeVisible();
    await waitFor(() =>
      expect(fetcher).toHaveBeenCalledWith(
        '/api/v1/notifications?limit=30&before=2026-08-10T08%3A00%3A00Z',
        expect.any(Object),
      ),
    );
  });

  it('renders the all-caught-up state without a fabricated notification list', async () => {
    document.cookie = 'zylora_user_csrf=notifications-test';
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ notifications: [], unread_count: 0, next_cursor: null }),
      }),
    );
    render(<NotificationsPanel />);

    expect(await screen.findByText('You are all caught up')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Mark as read' })).not.toBeInTheDocument();
  });
});
