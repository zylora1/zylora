import type { AnchorHTMLAttributes, ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react';

type ActionVariant = 'primary' | 'secondary' | 'quiet' | 'danger';

function classes(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(' ');
}

export function Button({
  variant = 'primary',
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ActionVariant }) {
  return <button className={classes('z-button', `z-button--${variant}`, className)} {...props} />;
}

export function ActionLink({
  variant = 'primary',
  className,
  ...props
}: AnchorHTMLAttributes<HTMLAnchorElement> & { variant?: ActionVariant }) {
  return <a className={classes('z-button', `z-button--${variant}`, className)} {...props} />;
}

export function StatusBadge({
  tone = 'neutral',
  children,
}: {
  tone?: 'neutral' | 'info' | 'success' | 'warning' | 'danger';
  children: ReactNode;
}) {
  return <span className={`z-status z-status--${tone}`}>{children}</span>;
}

export function Notice({
  tone = 'info',
  title,
  children,
  className,
}: {
  tone?: 'info' | 'success' | 'warning' | 'danger';
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={classes('z-notice', `z-notice--${tone}`, className)} role="status">
      <strong>{title}</strong>
      <div>{children}</div>
    </section>
  );
}

export function EmptyState({
  eyebrow,
  title,
  description,
  action,
  compact = false,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  action?: ReactNode;
  compact?: boolean;
}) {
  return (
    <section className={classes('z-empty', compact && 'z-empty--compact')}>
      {eyebrow ? <p className="z-empty__eyebrow">{eyebrow}</p> : null}
      <h2>{title}</h2>
      <p>{description}</p>
      {action ? <div className="z-empty__action">{action}</div> : null}
    </section>
  );
}

export function ErrorState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <section className="z-error" role="alert">
      <span className="z-error__mark" aria-hidden="true">
        !
      </span>
      <div>
        <h2>{title}</h2>
        <p>{description}</p>
        {action ? <div className="z-error__action">{action}</div> : null}
      </div>
    </section>
  );
}

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden="true" className={classes('z-skeleton', className)} {...props} />;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <header className="z-page-header">
      <div>
        {eyebrow ? <p className="z-page-header__eyebrow">{eyebrow}</p> : null}
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {action ? <div className="z-page-header__action">{action}</div> : null}
    </header>
  );
}
