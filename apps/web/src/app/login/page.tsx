import { Suspense } from 'react';

import { AuthForm } from '@/components/auth-form';
import { AuthShell } from '@/components/auth-shell';

export default function LoginPage() {
  return (
    <AuthShell
      eyebrow="Welcome back"
      title="Sign in to Zylora"
      description="Pick up where you left off. Your drafts and live website are waiting."
    >
      <Suspense fallback={<p>Preparing secure sign-in…</p>}>
        <AuthForm mode="login" />
      </Suspense>
    </AuthShell>
  );
}
