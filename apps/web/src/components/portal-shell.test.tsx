import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { PortalShell } from './portal-shell';

const mocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  csrfToken: vi.fn(),
  push: vi.fn(),
  pathname: '/app',
}));

vi.mock('@/lib/api', () => ({ apiRequest: mocks.apiRequest, csrfToken: mocks.csrfToken }));
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mocks.push }),
  usePathname: () => mocks.pathname,
}));
vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={String(href)} {...props}>
      {children}
    </a>
  ),
}));

describe('PortalShell', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.csrfToken.mockReset();
    mocks.push.mockReset();
    mocks.pathname = '/app';
  });

  it('renders the stable User workspace, active state, and responsive disclosure', async () => {
    mocks.apiRequest.mockResolvedValue({ email: 'person@example.com', account_type: 'USER' });
    render(
      <PortalShell>
        <h1>Workspace content</h1>
      </PortalShell>,
    );

    expect(await screen.findByRole('heading', { name: 'Workspace content' })).toBeVisible();
    const navigation = screen.getByRole('navigation', { name: 'User portal navigation' });
    expect(within(navigation).getAllByRole('link')).toHaveLength(10);
    expect(within(navigation).getByRole('link', { name: 'Overview' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    const menu = screen.getByRole('button', { name: 'Open navigation' });
    fireEvent.click(menu);
    expect(menu).toHaveAttribute('aria-expanded', 'true');
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(menu).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getByText('person@example.com')).toBeVisible();
  });

  it('keeps Super Admin navigation, API, CSRF cookie, and sign-out isolated', async () => {
    mocks.pathname = '/admin/audit';
    mocks.apiRequest
      .mockResolvedValueOnce({ email: 'operator@example.com', account_type: 'SUPER_ADMIN' })
      .mockResolvedValueOnce(undefined);
    mocks.csrfToken.mockReturnValue('admin-csrf');
    render(
      <PortalShell admin>
        <h1>Audit content</h1>
      </PortalShell>,
    );

    expect(await screen.findByRole('heading', { name: 'Audit content' })).toBeVisible();
    expect(screen.getByRole('navigation', { name: 'Super Admin navigation' })).toBeVisible();
    expect(screen.getByRole('link', { name: 'Audit' })).toHaveAttribute('aria-current', 'page');
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
    await waitFor(() =>
      expect(mocks.apiRequest).toHaveBeenLastCalledWith('/api/v1/admin/auth/logout', {
        method: 'POST',
        body: '{}',
        headers: { 'X-CSRF-Token': 'admin-csrf' },
      }),
    );
    expect(mocks.push).toHaveBeenCalledWith('/admin/login');
  });

  it('fails closed when identity cannot be verified', async () => {
    mocks.apiRequest.mockRejectedValue(new Error('expired'));
    render(
      <PortalShell>
        <h1>Private content</h1>
      </PortalShell>,
    );

    expect(await screen.findByRole('alert')).toHaveTextContent('Your session has ended');
    expect(screen.queryByRole('heading', { name: 'Private content' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login');
  });
});
