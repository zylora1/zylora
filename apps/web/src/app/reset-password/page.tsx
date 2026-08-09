import { Suspense } from 'react';

import { AuthForm } from '@/components/auth-form';
import { AuthShell } from '@/components/auth-shell';

export default function ResetPasswordPage() {
  return (
    <AuthShell
      eyebrow="Choose something strong"
      title="Set a new password"
      description="This one-time link expires shortly. Finishing will sign your account out on every device."
    >
      <Suspense fallback={<p>Checking your reset link…</p>}>
        <AuthForm mode="reset" />
      </Suspense>
    </AuthShell>
  );
}
