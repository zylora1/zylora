import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import ContactPage from './page';

const state = vi.hoisted(() => ({ required: false, apiRequest: vi.fn() }));

vi.mock('@/lib/api', () => ({ apiRequest: state.apiRequest }));
vi.mock('@/components/turnstile-widget', async () => {
  const React = await import('react');
  return {
    TurnstileWidget: ({
      onRequirementChange,
    }: {
      onRequirementChange: (required: boolean) => void;
    }) => {
      React.useEffect(() => onRequirementChange(state.required), [onRequirementChange]);
      return <div data-testid="turnstile" />;
    },
  };
});

function fillForm() {
  fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Ada Lovelace' } });
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'ada@example.com' } });
  fireEvent.change(screen.getByLabelText('Type of website you want'), {
    target: { value: 'Dental clinic website for specialized practice' },
  });
  fireEvent.change(screen.getByLabelText('Preferred contact time'), {
    target: { value: 'Weekdays 2-5 PM IST' },
  });
}

afterEach(() => {
  state.required = false;
  vi.clearAllMocks();
});

describe('ContactPage (Zylora Pro Enquiry)', () => {
  it('fails closed until a required security challenge has completed', async () => {
    state.required = true;
    render(<ContactPage />);
    fillForm();
    fireEvent.click(screen.getByRole('button', { name: 'Submit Pro Request' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Complete the security verification before sending.',
    );
    expect(state.apiRequest).not.toHaveBeenCalled();
  });

  it('submits a validated Pro enquiry and displays the reference ID confirmation', async () => {
    state.apiRequest.mockResolvedValue({
      id: 'pro-1',
      reference_id: 'ZPRO-849201',
      name: 'Ada Lovelace',
      email: 'ada@example.com',
      website_type: 'Dental clinic website for specialized practice',
      preferred_contact_time: 'Weekdays 2-5 PM IST',
      status: 'PENDING',
      submitted_at: '2026-08-16T22:00:00Z',
    });
    render(<ContactPage />);
    fillForm();
    fireEvent.click(screen.getByRole('button', { name: 'Submit Pro Request' }));

    await waitFor(() => expect(state.apiRequest).toHaveBeenCalledOnce());
    expect(state.apiRequest).toHaveBeenCalledWith(
      '/api/v1/public/pro-enquiry',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          name: 'Ada Lovelace',
          email: 'ada@example.com',
          website_type: 'Dental clinic website for specialized practice',
          preferred_contact_time: 'Weekdays 2-5 PM IST',
          company_website_url: null,
          turnstile_token: null,
        }),
      }),
    );
    expect(await screen.findByRole('status')).toHaveTextContent('ZPRO-849201');
  });

  it('shows the server error without losing an accessible retry path', async () => {
    state.apiRequest.mockRejectedValue(new Error('Too many Pro enquiries from this IP address.'));
    render(<ContactPage />);
    fillForm();
    fireEvent.click(screen.getByRole('button', { name: 'Submit Pro Request' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Too many Pro enquiries from this IP address.',
    );
    expect(screen.getByRole('button', { name: 'Submit Pro Request' })).toBeEnabled();
  });
});
