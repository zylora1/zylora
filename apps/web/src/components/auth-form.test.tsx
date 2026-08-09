import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AuthForm } from './auth-form';

vi.mock('@/components/turnstile-widget', async () => {
  const React = await import('react');
  return {
    TurnstileWidget: ({
      onToken,
      onRequirementChange,
    }: {
      onToken: (token: string | null) => void;
      onRequirementChange: (required: boolean) => void;
    }) => {
      React.useEffect(() => {
        onRequirementChange(false);
        onToken(null);
      }, [onRequirementChange, onToken]);
      return null;
    },
  };
});

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

describe('AuthForm', () => {
  afterEach(() => vi.restoreAllMocks());

  it('renders the complete User login path without admin affordances', () => {
    render(<AuthForm mode="login" />);

    expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeVisible();
    expect(screen.getByLabelText('Email address')).toHaveAttribute('autocomplete', 'email');
    expect(screen.getByLabelText('Password')).toHaveAttribute('autocomplete', 'current-password');
    expect(screen.queryByText(/administration/i)).not.toBeInTheDocument();
  });

  it('shows safe API errors and does not navigate', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Email or password is incorrect.' }), {
        status: 401,
      }),
    );
    render(<AuthForm mode="login" />);

    fireEvent.change(screen.getByLabelText('Email address'), {
      target: { value: 'person@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'Wrong-password-42!' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Email or password is incorrect.');
  });

  it('uses the generic account-recovery response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ status: 'accepted' }), { status: 202 }),
    );
    render(<AuthForm mode="forgot" />);
    fireEvent.change(screen.getByLabelText('Email address'), {
      target: { value: 'person@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send reset link' }));

    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent(
        'If that account exists, a secure reset link is on its way.',
      ),
    );
  });

  it('keeps Super Admin login free of Google and User registration links', () => {
    render(<AuthForm mode="admin-login" />);

    expect(screen.getByRole('button', { name: 'Enter administration' })).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Continue with Google' })).not.toBeInTheDocument();
    expect(screen.queryByText(/create an account/i)).not.toBeInTheDocument();
  });
});
