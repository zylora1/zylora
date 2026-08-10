import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const navigationState = vi.hoisted(() => ({ token: 'a'.repeat(32) }));
vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(`token=${navigationState.token}`),
}));

import UnsubscribePage from './page';

afterEach(() => vi.unstubAllGlobals());

describe('marketing unsubscribe', () => {
  it('sends only the opaque token to the public preference endpoint', async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, status: 204 });
    vi.stubGlobal('fetch', fetcher);

    render(<UnsubscribePage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Unsubscribe from marketing' }));

    await waitFor(() =>
      expect(fetcher).toHaveBeenCalledWith(
        '/api/v1/public/marketing/unsubscribe',
        expect.objectContaining({
          body: JSON.stringify({ token: navigationState.token }),
          credentials: 'include',
        }),
      ),
    );
    expect(
      await screen.findByText('You have been unsubscribed from Zylora marketing email.'),
    ).toBeVisible();
  });
});
