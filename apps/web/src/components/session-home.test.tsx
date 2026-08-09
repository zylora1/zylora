import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { SessionHome } from './session-home';

const mocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  csrfToken: vi.fn(),
  push: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  apiRequest: mocks.apiRequest,
  csrfToken: mocks.csrfToken,
}));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: mocks.push }) }));

describe('SessionHome', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.csrfToken.mockReset();
    mocks.push.mockReset();
  });

  it('loads the User identity and signs out with double-submit CSRF', async () => {
    mocks.apiRequest.mockResolvedValueOnce({ email: 'person@example.com', account_type: 'USER' });
    mocks.apiRequest.mockResolvedValueOnce(undefined);
    mocks.csrfToken.mockReturnValue('csrf-value');
    render(<SessionHome />);

    expect(
      await screen.findByRole('heading', { name: 'Welcome, person@example.com' }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));

    await waitFor(() =>
      expect(mocks.apiRequest).toHaveBeenLastCalledWith('/api/v1/auth/logout', {
        method: 'POST',
        body: '{}',
        headers: { 'X-CSRF-Token': 'csrf-value' },
      }),
    );
    expect(mocks.push).toHaveBeenCalledWith('/login');
  });

  it('keeps the admin API, cookie, copy, and redirect isolated', async () => {
    mocks.apiRequest.mockResolvedValueOnce({
      email: 'operator@example.com',
      account_type: 'SUPER_ADMIN',
    });
    mocks.apiRequest.mockRejectedValueOnce(new Error('revoked'));
    render(<SessionHome admin />);

    expect(await screen.findByText(/isolated administration boundary/i)).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));

    await waitFor(() => expect(mocks.csrfToken).toHaveBeenCalledWith('zylora_admin_csrf'));
    expect(mocks.apiRequest).toHaveBeenLastCalledWith('/api/v1/admin/auth/logout', {
      method: 'POST',
      body: '{}',
      headers: {},
    });
    expect(mocks.push).toHaveBeenCalledWith('/admin/login');
  });

  it('renders an expired-session recovery path', async () => {
    mocks.apiRequest.mockRejectedValueOnce(new Error('expired'));
    render(<SessionHome />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Your session has ended. Sign in again to continue.',
    );
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login');
  });
});
