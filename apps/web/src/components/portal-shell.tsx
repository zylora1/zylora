'use client';

import { ActionLink, ErrorState, Skeleton, StatusBadge } from '@zylora/ui';
import {
  BadgeDollarSign,
  Bell,
  ChartNoAxesCombined,
  CircleGauge,
  Coins,
  Contact,
  Globe2,
  HeartPulse,
  Home,
  LayoutTemplate,
  Library,
  LogOut,
  Mail,
  Menu,
  PanelsTopLeft,
  ReceiptText,
  ScrollText,
  Settings,
  SlidersHorizontal,
  Users,
  X,
} from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import type { ComponentType, ReactNode } from 'react';

import { apiRequest, csrfToken } from '@/lib/api';
import { BrandMark } from './brand-mark';

type Identity = { email: string; account_type: 'USER' | 'SUPER_ADMIN' };
type NavigationItem = { href: string; label: string; icon: ComponentType<{ size?: number }> };

const userNavigation: NavigationItem[] = [
  { href: '/app', label: 'Home', icon: Home },
  { href: '/app/websites', label: 'Websites', icon: PanelsTopLeft },
  { href: '/app/templates', label: 'Templates', icon: LayoutTemplate },
  { href: '/app/leads', label: 'Leads', icon: Contact },
  { href: '/app/analytics', label: 'Analytics', icon: ChartNoAxesCombined },
  { href: '/app/credits', label: 'Credits', icon: Coins },
  { href: '/app/billing', label: 'Billing', icon: ReceiptText },
  { href: '/app/domains', label: 'Domains', icon: Globe2 },
  { href: '/app/notifications', label: 'Notifications', icon: Bell },
  { href: '/app/settings', label: 'Settings', icon: Settings },
];

const adminNavigation: NavigationItem[] = [
  { href: '/admin', label: 'Overview', icon: CircleGauge },
  { href: '/admin/users', label: 'Users', icon: Users },
  { href: '/admin/websites', label: 'Websites', icon: PanelsTopLeft },
  { href: '/admin/templates', label: 'Templates', icon: Library },
  { href: '/admin/commerce', label: 'Commerce', icon: BadgeDollarSign },
  { href: '/admin/leads-credits', label: 'Leads & credits', icon: Contact },
  { href: '/admin/domains', label: 'Domains', icon: Globe2 },
  { href: '/admin/communications', label: 'Content & email', icon: Mail },
  { href: '/admin/health', label: 'Health', icon: HeartPulse },
  { href: '/admin/audit', label: 'Audit', icon: ScrollText },
  { href: '/admin/configuration', label: 'Configuration', icon: SlidersHorizontal },
];

export function PortalShell({ admin = false, children }: { admin?: boolean; children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [failed, setFailed] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const navigation = admin ? adminNavigation : userNavigation;

  useEffect(() => {
    let active = true;
    apiRequest<Identity>(admin ? '/api/v1/admin/me' : '/api/v1/auth/me')
      .then((result) => {
        if (active) setIdentity(result);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [admin]);

  useEffect(() => {
    if (!menuOpen) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setMenuOpen(false);
    }
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [menuOpen]);

  async function logout() {
    const token = csrfToken(admin ? 'zylora_admin_csrf' : 'zylora_user_csrf');
    try {
      await apiRequest(admin ? '/api/v1/admin/auth/logout' : '/api/v1/auth/logout', {
        method: 'POST',
        body: '{}',
        headers: token ? { 'X-CSRF-Token': token } : {},
      });
    } catch {
      // The protected screen still closes when the server has already ended the session.
    } finally {
      router.push(admin ? '/admin/login' : '/login');
    }
  }

  const current = navigation.find((item) =>
    item.href === (admin ? '/admin' : '/app')
      ? pathname === item.href
      : pathname.startsWith(`${item.href}/`) || pathname === item.href,
  );

  return (
    <div className={admin ? 'workspace-shell workspace-shell--admin' : 'workspace-shell'}>
      <a className="skip-link" href="#workspace-content">
        Skip to content
      </a>
      <button
        aria-hidden={!menuOpen}
        aria-label="Close navigation"
        className={menuOpen ? 'workspace-scrim workspace-scrim--visible' : 'workspace-scrim'}
        tabIndex={menuOpen ? 0 : -1}
        type="button"
        onClick={() => setMenuOpen(false)}
      />
      <aside
        className={menuOpen ? 'workspace-sidebar workspace-sidebar--open' : 'workspace-sidebar'}
        id="portal-navigation"
      >
        <div className="workspace-sidebar__brand">
          <BrandMark admin={admin} href={admin ? '/admin' : '/app'} />
          <button
            aria-label="Close navigation"
            className="workspace-sidebar__close"
            type="button"
            onClick={() => setMenuOpen(false)}
          >
            <X size={20} />
          </button>
        </div>
        <nav
          aria-label={admin ? 'Super Admin navigation' : 'User portal navigation'}
          className="workspace-navigation"
        >
          <p className="workspace-navigation__label">{admin ? 'Operations' : 'Workspace'}</p>
          {navigation.map((item) => {
            const Icon = item.icon;
            const active = current?.href === item.href;
            return (
              <Link
                aria-current={active ? 'page' : undefined}
                className={
                  active
                    ? 'workspace-navigation__link workspace-navigation__link--active'
                    : 'workspace-navigation__link'
                }
                href={item.href}
                key={item.href}
                onClick={() => setMenuOpen(false)}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="workspace-account">
          {identity ? (
            <>
              <span className="workspace-account__avatar" aria-hidden="true">
                {identity.email.slice(0, 1).toUpperCase()}
              </span>
              <span className="workspace-account__identity">
                <strong>{admin ? 'Super Admin' : 'Your account'}</strong>
                <small title={identity.email}>{identity.email}</small>
              </span>
            </>
          ) : (
            <>
              <Skeleton className="workspace-account__avatar" />
              <Skeleton className="workspace-account__identity" />
            </>
          )}
          <button
            aria-label="Sign out"
            className="workspace-account__logout"
            type="button"
            onClick={logout}
          >
            <LogOut size={18} />
          </button>
        </div>
      </aside>
      <div className="workspace-stage">
        <header className="workspace-topbar">
          <button
            aria-controls="portal-navigation"
            aria-expanded={menuOpen}
            aria-label="Open navigation"
            className="workspace-menu"
            type="button"
            onClick={() => setMenuOpen(true)}
          >
            <Menu size={21} />
          </button>
          <div>
            <span>{admin ? 'Super Admin' : 'Zylora'}</span>
            <strong>{current?.label ?? 'Workspace'}</strong>
          </div>
          <StatusBadge tone={failed ? 'danger' : identity ? 'success' : 'neutral'}>
            {failed ? 'Session ended' : identity ? 'Secure session' : 'Checking session'}
          </StatusBadge>
        </header>
        <main className="workspace-content" id="workspace-content">
          {failed ? (
            <ErrorState
              title="Your session has ended"
              description="Sign in again to continue. No account data is shown without a verified session."
              action={<ActionLink href={admin ? '/admin/login' : '/login'}>Sign in</ActionLink>}
            />
          ) : identity ? (
            children
          ) : (
            <PortalShellLoading />
          )}
        </main>
      </div>
    </div>
  );
}

export function PortalShellLoading() {
  return (
    <div className="workspace-loading" role="status" aria-label="Loading workspace">
      <Skeleton className="workspace-loading__eyebrow" />
      <Skeleton className="workspace-loading__title" />
      <Skeleton className="workspace-loading__body" />
      <Skeleton className="workspace-loading__panel" />
    </div>
  );
}
