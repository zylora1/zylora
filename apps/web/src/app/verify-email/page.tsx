import { Suspense } from 'react';

import { AuthForm } from '@/components/auth-form';
import { AuthShell } from '@/components/auth-shell';

export default function VerifyEmailPage() {
  return (
    <AuthShell
      eyebrow="Check your inbox"
      title="Verify your email"
      description="Enter the six-digit code we sent you. It expires after 15 minutes and works once."
    >
      <Suspense fallback={<p>Preparing verification…</p>}>
        <AuthForm mode="verify" />
      </Suspense>
    </AuthShell>
  );
}
