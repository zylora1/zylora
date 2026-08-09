import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

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

const navigation = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: navigation.push }),
  useSearchParams: () => new URLSearchParams('token=secure-reset-token'),
}));

function successfulResponse(status = 200) {
  return new Response(JSON.stringify({ status: 'accepted' }), { status });
}

function fillCredentials(email = 'person@example.com', password = 'Strong-Password-42!') {
  fireEvent.change(screen.getByLabelText('Email address'), { target: { value: email } });
  fireEvent.change(document.querySelector('input[name="password"]')!, {
    target: { value: password },
  });
}

describe('AuthForm state transitions', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    navigation.push.mockReset();
  });

  it('routes a successful signup into email verification', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(successfulResponse(202));
    render(<AuthForm mode="signup" />);
    fillCredentials();
    expect(screen.getByText(/12\+ characters/i)).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));

    await waitFor(() =>
      expect(navigation.push).toHaveBeenCalledWith('/verify-email?email=person%40example.com'),
    );
  });

  it.each([
    ['login', 'Sign in', '/app'],
    ['admin-login', 'Enter administration', '/admin'],
  ] as const)('routes a successful %s session', async (mode, button, destination) => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(successfulResponse());
    render(<AuthForm mode={mode} />);
    fillCredentials();
    fireEvent.click(screen.getByRole('button', { name: button }));

    await waitFor(() => expect(navigation.push).toHaveBeenCalledWith(destination));
  });

  it('accepts only digits, resends safely, and completes verification', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(successfulResponse(202))
      .mockResolvedValueOnce(successfulResponse());
    render(<AuthForm mode="verify" />);
    fireEvent.change(screen.getByLabelText('Email address'), {
      target: { value: 'person@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Six-digit code'), { target: { value: '12x34-56' } });
    expect(screen.getByLabelText('Six-digit code')).toHaveValue('123456');
    fireEvent.click(screen.getByRole('button', { name: 'Send a new code' }));
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Earlier codes will no longer work.',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Verify email' }));

    await waitFor(() => expect(navigation.push).toHaveBeenCalledWith('/login'));
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('submits the one-time reset token and returns to login', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(successfulResponse());
    render(<AuthForm mode="reset" />);
    fireEvent.change(document.querySelector('input[name="password"]')!, {
      target: { value: 'Changed-Password-42!' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Set new password' }));

    await waitFor(() => expect(navigation.push).toHaveBeenCalledWith('/login'));
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/auth/password-reset/confirm',
      expect.objectContaining({
        body: JSON.stringify({
          token: 'secure-reset-token',
          new_password: 'Changed-Password-42!',
        }),
      }),
    );
  });

  it('renders provider and resend failures without trusting them', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Google sign-in is temporarily unavailable.' }), {
        status: 503,
      }),
    );
    render(<AuthForm mode="login" />);
    fireEvent.click(screen.getByRole('button', { name: 'Continue with Google' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Google sign-in is temporarily unavailable.',
    );

    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Email delivery is temporarily unavailable.' }), {
        status: 503,
      }),
    );
  });
});
