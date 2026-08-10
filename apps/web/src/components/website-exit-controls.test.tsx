import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { WebsiteExitControls } from './website-exit-controls';

afterEach(() => vi.unstubAllGlobals());

describe('Phase 9 Website exit controls', () => {
  it('requires recipient validation and explicit confirmation before transfer', async () => {
    const fetcher = vi.fn().mockImplementation((path: string, options?: RequestInit) => {
      if (path.endsWith('/transfers/validate')) {
        expect(options?.body).toBe(JSON.stringify({ recipient_email: 'new-owner@example.com' }));
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            website_id: 'website-id',
            recipient_email: 'new-owner@example.com',
            eligible: true,
            requires_route_deactivation: true,
          }),
        });
      }
      expect(options?.body).toBe(
        JSON.stringify({
          recipient_email: 'new-owner@example.com',
          confirmation_version: 'OWNER_TRANSFER_V1',
        }),
      );
      return Promise.resolve({
        ok: true,
        status: 202,
        json: async () => ({ status: 'DEACTIVATING' }),
      });
    });
    vi.stubGlobal('fetch', fetcher);
    render(<WebsiteExitControls websiteId="website-id" />);

    const transfer = screen.getByRole('button', { name: 'Transfer Website' });
    expect(transfer).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Transfer recipient email'), {
      target: { value: 'new-owner@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Validate recipient' }));
    expect(await screen.findByText(/routing will be disabled first/i)).toBeVisible();
    expect(transfer).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(transfer);
    expect(await screen.findByText(/waiting for public routing/i)).toBeVisible();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it('shows only the server snapshot and unavailable-provider status for paid ZIP checkout', async () => {
    const fetcher = vi.fn().mockImplementation((path: string) => {
      if (path.endsWith('/exports')) {
        return Promise.resolve({
          ok: true,
          status: 201,
          json: async () => ({
            id: 'purchase-id',
            status: 'CREATED',
            price: { amount_minor: 1900, currency: 'USD' },
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({
          purchase: {
            id: 'purchase-id',
            status: 'PAYMENT_PENDING',
            price: { amount_minor: 1900, currency: 'USD' },
          },
          provider_available: false,
          detail: 'Paid checkout remains unavailable until an approved provider is configured.',
        }),
      });
    });
    vi.stubGlobal('fetch', fetcher);
    render(<WebsiteExitControls websiteId="website-id" />);

    fireEvent.click(screen.getByRole('button', { name: 'Price Website ZIP export' }));
    expect(await screen.findByText('$19 snapshot ready.')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Proceed to secure checkout' }));
    expect(await screen.findByText(/approved provider/i)).toBeVisible();
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  });
});
