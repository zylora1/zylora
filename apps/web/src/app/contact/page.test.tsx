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
  fireEvent.change(screen.getByLabelText('Message'), {
    target: { value: 'Please help us choose an approved Template.' },
  });
}

afterEach(() => {
  state.required = false;
  vi.clearAllMocks();
});

describe('ContactPage', () => {
  it('fails closed until a required security challenge has completed', async () => {
    state.required = true;
    render(<ContactPage />);
    fillForm();
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Complete the security verification before sending.',
    );
    expect(state.apiRequest).not.toHaveBeenCalled();
  });

  it('submits a validated message to the public contact command and confirms delivery', async () => {
    state.apiRequest.mockResolvedValue({ status: 'accepted', id: 'contact-id' });
    render(<ContactPage />);
    fillForm();
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => expect(state.apiRequest).toHaveBeenCalledOnce());
    expect(state.apiRequest).toHaveBeenCalledWith(
      '/api/v1/public/contact',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          name: 'Ada Lovelace',
          email: 'ada@example.com',
          message: 'Please help us choose an approved Template.',
          turnstile_token: null,
        }),
      }),
    );
    expect(await screen.findByRole('status')).toHaveTextContent('safely queued');
  });

  it('shows the server error without losing an accessible retry path', async () => {
    state.apiRequest.mockRejectedValue(new Error('Contact is temporarily unavailable.'));
    render(<ContactPage />);
    fillForm();
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Contact is temporarily unavailable.',
    );
    expect(screen.getByRole('button', { name: 'Send message' })).toBeEnabled();
  });
});
