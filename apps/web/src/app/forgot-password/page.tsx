import { Suspense } from 'react';

import { AuthForm } from '@/components/auth-form';
import { AuthShell } from '@/components/auth-shell';

export default function ForgotPasswordPage() {
  return (
    <AuthShell
      eyebrow="Account recovery"
      title="Reset your password"
      description="Tell us where to send a one-time reset link. For privacy, every request gets the same response."
    >
      <Suspense fallback={<p>Preparing account recovery…</p>}>
        <AuthForm mode="forgot" />
      </Suspense>
    </AuthShell>
  );
}
