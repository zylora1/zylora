import { Suspense } from 'react';

import { AuthForm } from '@/components/auth-form';
import { AuthShell } from '@/components/auth-shell';

export default function AdminLoginPage() {
  return (
    <AuthShell
      admin
      eyebrow="Isolated access"
      title="Super Admin sign in"
      description="This application is separate from the User portal. Access is limited, short-lived, and audited."
    >
      <Suspense fallback={<p>Preparing restricted sign-in…</p>}>
        <AuthForm mode="admin-login" />
      </Suspense>
    </AuthShell>
  );
}
