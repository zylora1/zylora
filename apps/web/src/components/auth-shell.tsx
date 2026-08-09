import type { ReactNode } from 'react';

import { BrandMark } from './brand-mark';

export function AuthShell({
  eyebrow,
  title,
  description,
  children,
  admin = false,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
  admin?: boolean;
}) {
  return (
    <main className={admin ? 'auth-shell auth-shell--admin' : 'auth-shell'}>
      <section className="auth-story" aria-label="Zylora introduction">
        <BrandMark admin={admin} />
        <div className="auth-story__copy">
          <p className="eyebrow">
            {admin ? 'Restricted operations' : 'Websites, thoughtfully made'}
          </p>
          <p className="display-quote">
            {admin
              ? 'A separate door for the people who keep Zylora dependable.'
              : 'Your next chapter deserves a place of its own.'}
          </p>
        </div>
        <p className="auth-story__foot">Structured. Secure. Yours.</p>
      </section>
      <section className="auth-workspace" aria-labelledby="auth-title">
        <div className="auth-workspace__inner">
          <p className="eyebrow">{eyebrow}</p>
          <h1 id="auth-title">{title}</h1>
          <p className="auth-description">{description}</p>
          {children}
        </div>
      </section>
    </main>
  );
}
