import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

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

describe('verification resend failure', () => {
  it('shows a safe delivery failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Email delivery is temporarily unavailable.' }), {
        status: 503,
      }),
    );
    render(<AuthForm mode="verify" />);
    fireEvent.change(screen.getByLabelText('Email address'), {
      target: { value: 'person@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send a new code' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Email delivery is temporarily unavailable.',
    );
  });
});
