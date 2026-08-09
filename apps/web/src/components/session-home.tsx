'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { apiRequest, csrfToken } from '@/lib/api';
import { BrandMark } from './brand-mark';

type User = { email: string; account_type: 'USER' | 'SUPER_ADMIN' };

export function SessionHome({ admin = false }: { admin?: boolean }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    apiRequest<User>(admin ? '/api/v1/admin/me' : '/api/v1/auth/me')
      .then((result) => {
        if (active) setUser(result);
      })
      .catch(() => {
        if (active) setError('Your session has ended. Sign in again to continue.');
      });
    return () => {
      active = false;
    };
  }, [admin]);

  async function logout() {
    const cookieName = admin ? 'zylora_admin_csrf' : 'zylora_user_csrf';
    const token = csrfToken(cookieName);
    try {
      await apiRequest(admin ? '/api/v1/admin/auth/logout' : '/api/v1/auth/logout', {
        method: 'POST',
        body: '{}',
        headers: token ? { 'X-CSRF-Token': token } : {},
      });
    } catch {
      // Local navigation still clears the protected screen when the session is already gone.
    } finally {
      router.push(admin ? '/admin/login' : '/login');
    }
  }

  return (
    <main className={admin ? 'portal-shell portal-shell--admin' : 'portal-shell'}>
      <nav className="portal-nav">
        <BrandMark admin={admin} />
        <button className="secondary-button" type="button" onClick={logout}>
          Sign out
        </button>
      </nav>
      <section className="portal-welcome">
        <p className="eyebrow">{admin ? 'Operations' : 'Your Zylora'}</p>
        <h1>{user ? `Welcome, ${user.email}` : admin ? 'Super Admin' : 'Welcome back'}</h1>
        {error ? (
          <p className="form-message form-message--error" role="alert">
            {error} <a href={admin ? '/admin/login' : '/login'}>Sign in</a>
          </p>
        ) : (
          <p className="auth-description">
            {admin
              ? 'The isolated administration boundary is active. Operational modules arrive in their owning phases.'
              : 'Your verified identity boundary is ready. Website creation begins in its owning phase.'}
          </p>
        )}
      </section>
    </main>
  );
}
