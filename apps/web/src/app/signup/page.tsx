import { Suspense } from 'react';

import { AuthForm } from '@/components/auth-form';
import { AuthShell } from '@/components/auth-shell';

export default function SignupPage() {
  return (
    <AuthShell
      eyebrow="Start something good"
      title="Create your account"
      description="One account for your drafts, your published website, and everything still taking shape."
    >
      <Suspense fallback={<p>Preparing your account…</p>}>
        <AuthForm mode="signup" />
      </Suspense>
    </AuthShell>
  );
}
