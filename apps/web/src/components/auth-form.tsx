'use client';

import { Eye, EyeOff } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useState } from 'react';
import type { FormEvent } from 'react';

import { TurnstileWidget } from '@/components/turnstile-widget';
import type { TurnstileAction } from '@/components/turnstile-widget';
import { apiRequest } from '@/lib/api';
import { currentAttribution } from '@/lib/attribution';
import { storedAiPrompt } from '@/lib/ai-builder';

type Mode = 'login' | 'signup' | 'verify' | 'forgot' | 'reset' | 'admin-login';
type AuthResult = { csrf_token: string; user: { email: string } };

const challengeActions: Record<Mode, TurnstileAction> = {
  login: 'login',
  signup: 'signup',
  verify: 'verify_email',
  forgot: 'password_recovery',
  reset: 'password_recovery',
  'admin-login': 'admin_login',
};

const copy: Record<Mode, { endpoint: string; submit: string; busy: string }> = {
  login: { endpoint: '/api/v1/auth/login', submit: 'Sign in', busy: 'Signing in...' },
  signup: { endpoint: '/api/v1/auth/signup', submit: 'Create account', busy: 'Creating...' },
  verify: { endpoint: '/api/v1/auth/verify-email', submit: 'Verify email', busy: 'Verifying...' },
  forgot: {
    endpoint: '/api/v1/auth/password-reset/request',
    submit: 'Send reset link',
    busy: 'Sending...',
  },
  reset: {
    endpoint: '/api/v1/auth/password-reset/confirm',
    submit: 'Set new password',
    busy: 'Updating...',
  },
  'admin-login': {
    endpoint: '/api/v1/admin/auth/login',
    submit: 'Enter administration',
    busy: 'Checking access...',
  },
};

export function AuthForm({ mode }: { mode: Mode }) {
  const router = useRouter();
  const search = useSearchParams();
  const [email, setEmail] = useState(search.get('email') ?? '');
  const [password, setPassword] = useState('');
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [code, setCode] = useState('');
  const [error, setError] = useState(
    search.get('oauth_error') ? 'Google sign-in could not be completed. Please try again.' : '',
  );
  const [notice, setNotice] = useState('');
  const [pending, setPending] = useState(false);
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [challengeRequired, setChallengeRequired] = useState<boolean | null>(null);
  const [challengeResetKey, setChallengeResetKey] = useState(0);
  const asksEmail = mode !== 'reset';
  const asksPassword = ['login', 'signup', 'reset', 'admin-login'].includes(mode);
  const challengeReady = challengeRequired === false || Boolean(turnstileToken);
  const acceptToken = useCallback((token: string | null) => setTurnstileToken(token), []);
  const setRequirement = useCallback((required: boolean) => setChallengeRequired(required), []);
  const setChallengeError = useCallback((message: string) => setError(message), []);
  const resetChallenge = useCallback(() => {
    setTurnstileToken(null);
    setChallengeResetKey((current) => current + 1);
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setNotice('');
    setPending(true);
    try {
      const challenge = { turnstile_token: turnstileToken ?? undefined };
      const body =
        mode === 'verify'
          ? { email, code, ...challenge }
          : mode === 'reset'
            ? { token: search.get('token') ?? '', new_password: password, ...challenge }
            : {
                email,
                ...(asksPassword ? { password } : {}),
                ...(mode === 'signup' ? { attribution: currentAttribution() } : {}),
                ...challenge,
              };
      const result = await apiRequest<AuthResult>(copy[mode].endpoint, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (mode === 'login') router.push(storedAiPrompt() ? '/app/ai-builder' : '/app');
      else if (mode === 'admin-login') router.push('/admin');
      else if (mode === 'signup') router.push(`/verify-email?email=${encodeURIComponent(email)}`);
      else if (mode === 'verify' || mode === 'reset') router.push('/login');
      else setNotice('If that account exists, a secure reset link is on its way.');
      void result;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'We could not complete that request.');
    } finally {
      resetChallenge();
      setPending(false);
    }
  }

  async function googleSignIn() {
    setError('');
    setPending(true);
    try {
      const result = await apiRequest<{ authorization_url: string }>('/api/v1/auth/google/start', {
        method: 'POST',
        body: JSON.stringify({
          turnstile_token: turnstileToken ?? undefined,
          attribution: currentAttribution(),
        }),
      });
      window.location.assign(result.authorization_url);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Google sign-in is unavailable.');
      resetChallenge();
      setPending(false);
    }
  }

  async function resend() {
    setError('');
    try {
      await apiRequest('/api/v1/auth/resend-verification', {
        method: 'POST',
        body: JSON.stringify({ email, turnstile_token: turnstileToken ?? undefined }),
      });
      setNotice('A fresh code is on its way. Earlier codes will no longer work.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'A new code could not be sent.');
    } finally {
      resetChallenge();
    }
  }

  return (
    <>
      {mode === 'login' || mode === 'signup' ? (
        <button
          className="google-button"
          type="button"
          onClick={googleSignIn}
          disabled={pending || !challengeReady}
        >
          <svg
            className="google-glyph-svg"
            width="18"
            height="18"
            viewBox="0 0 18 18"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            <path
              fill="#4285F4"
              d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.259h2.908c1.702-1.567 2.684-3.874 2.684-6.617z"
            />
            <path
              fill="#34A853"
              d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z"
            />
            <path
              fill="#FBBC05"
              d="M3.964 10.71A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 000 9c0 1.452.348 2.827.957 4.042l3.007-2.332z"
            />
            <path
              fill="#EA4335"
              d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z"
            />
          </svg>
          Continue with Google
        </button>
      ) : null}
      {mode === 'login' || mode === 'signup' ? (
        <div className="divider">or use your email</div>
      ) : null}
      <form className="auth-form" onSubmit={submit}>
        {asksEmail ? (
          <label>
            Email address
            <input
              autoComplete="email"
              name="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
        ) : null}
        {mode === 'verify' ? (
          <label>
            Six-digit code
            <input
              autoComplete="one-time-code"
              className="code-input"
              inputMode="numeric"
              maxLength={6}
              name="code"
              pattern="[0-9]{6}"
              value={code}
              onChange={(event) => setCode(event.target.value.replace(/\D/g, ''))}
              required
            />
          </label>
        ) : null}
        {asksPassword ? (
          <div className="auth-field">
            <label htmlFor={`${mode}-password`}>
              {mode === 'reset' ? 'New password' : 'Password'}
            </label>
            <span className="password-field">
              <input
                autoComplete={
                  mode === 'signup' || mode === 'reset' ? 'new-password' : 'current-password'
                }
                id={`${mode}-password`}
                minLength={mode === 'signup' || mode === 'reset' ? 12 : 1}
                name="password"
                type={passwordVisible ? 'text' : 'password'}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
              <button
                aria-label={passwordVisible ? 'Hide password' : 'Show password'}
                className="password-toggle"
                type="button"
                onClick={() => setPasswordVisible((current) => !current)}
              >
                {passwordVisible ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </span>
            {mode === 'signup' || mode === 'reset' ? (
              <span className="field-hint">
                12+ characters with upper, lower, number, and symbol.
              </span>
            ) : null}
          </div>
        ) : null}
        <TurnstileWidget
          action={challengeActions[mode]}
          resetKey={challengeResetKey}
          onToken={acceptToken}
          onRequirementChange={setRequirement}
          onError={setChallengeError}
        />
        {error ? (
          <p className="form-message form-message--error" role="alert">
            {error}
          </p>
        ) : null}
        {notice ? (
          <p className="form-message form-message--success" role="status">
            {notice}
          </p>
        ) : null}
        <button className="primary-button" type="submit" disabled={pending || !challengeReady}>
          {pending ? copy[mode].busy : copy[mode].submit}
        </button>
      </form>
      {mode === 'verify' ? (
        <button className="text-button" type="button" onClick={resend} disabled={!challengeReady}>
          Send a new code
        </button>
      ) : null}
      <AuthLinks mode={mode} />
    </>
  );
}

function AuthLinks({ mode }: { mode: Mode }) {
  if (mode === 'admin-login') return <p className="auth-footnote">Authorized operators only.</p>;
  if (mode === 'login') {
    return (
      <div className="auth-links">
        <a href="/forgot-password">Forgot password?</a>
        <span>
          New here? <a href="/signup">Create an account</a>
        </span>
      </div>
    );
  }
  return (
    <p className="auth-footnote">
      Already have an account? <a href="/login">Sign in</a>
    </p>
  );
}
