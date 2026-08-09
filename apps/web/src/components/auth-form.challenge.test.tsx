import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { AuthForm } from './auth-form';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

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
        onRequirementChange(true);
        onToken('single-use-form-token');
      }, [onRequirementChange, onToken]);
      return <div aria-label="Security verification" />;
    },
  };
});

describe('AuthForm challenge contract', () => {
  it('includes the challenge token in a protected login command', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
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
    await waitFor(() => expect(screen.getByRole('button', { name: 'Sign in' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/v1/auth/login',
        expect.objectContaining({
          body: JSON.stringify({
            email: 'person@example.com',
            password: 'Wrong-password-42!',
            turnstile_token: 'single-use-form-token',
          }),
        }),
      ),
    );
  });
});
