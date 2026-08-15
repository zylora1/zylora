'use client';

import { ArrowUpRight, Menu, X } from 'lucide-react';
import Link from 'next/link';
import type { ReactNode } from 'react';
import { useEffect, useRef, useState } from 'react';

import { BrandMark } from './brand-mark';
import styles from './public-site.module.css';

const navigation = [
  { href: '/#product', label: 'Product' },
  { href: '/ai-website-builder', label: 'AI Builder' },
  { href: '/templates', label: 'Templates' },
  { href: '/features', label: 'Features' },
  { href: '/pricing', label: 'Pricing' },
] as const;

export function PublicSite({ children }: { children: ReactNode }) {
  return <div className={styles.site}>{children}</div>;
}

export function PublicNavigation() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [hidden, setHidden] = useState(false);
  const lastScroll = useRef(0);
  const frame = useRef<number | null>(null);

  useEffect(() => {
    const update = () => {
      if (frame.current !== null) return;
      frame.current = window.requestAnimationFrame(() => {
        const current = window.scrollY;
        const nextScrolled = current > 16;
        const nextHidden = !open && current > 180 && current > lastScroll.current + 5;
        setScrolled((value) => (value === nextScrolled ? value : nextScrolled));
        setHidden((value) => (value === nextHidden ? value : nextHidden));
        lastScroll.current = current;
        frame.current = null;
      });
    };

    update();
    window.addEventListener('scroll', update, { passive: true });
    return () => {
      window.removeEventListener('scroll', update);
      if (frame.current !== null) window.cancelAnimationFrame(frame.current);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [open]);

  const toggleMenu = () => {
    setHidden(false);
    setOpen((current) => !current);
  };

  return (
    <header className={styles.header} data-scrolled={scrolled} data-hidden={hidden}>
      <nav className={styles.navigation} aria-label="Primary navigation">
        <BrandMark />
        <div className={styles.navLinks}>
          {navigation.map((item) => (
            <Link href={item.href} key={item.href}>
              {item.label}
            </Link>
          ))}
        </div>
        <div className={styles.navActions}>
          <Link className={styles.signIn} href="/login">
            Sign in
          </Link>
          <Link className={styles.navCta} href="/signup">
            Start building <ArrowUpRight aria-hidden="true" size={15} />
          </Link>
          <button
            type="button"
            className={styles.menuButton}
            aria-label={open ? 'Close navigation menu' : 'Open navigation menu'}
            aria-expanded={open}
            aria-controls="mobile-navigation"
            onClick={toggleMenu}
          >
            {open ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
          </button>
        </div>
      </nav>
      <div className={styles.mobileMenu} id="mobile-navigation" data-open={open} hidden={!open}>
        {navigation.map((item) => (
          <Link href={item.href} key={item.href} onClick={() => setOpen(false)}>
            {item.label}
          </Link>
        ))}
        <Link href="/login" onClick={() => setOpen(false)}>
          Sign in
        </Link>
        <Link className={styles.mobileCta} href="/signup" onClick={() => setOpen(false)}>
          Start building
        </Link>
      </div>
    </header>
  );
}

export function PublicFooter() {
  return (
    <footer className={styles.footer}>
      <div className={styles.footerLead}>
        <BrandMark />
        <p>
          AI-generated and Template-first Websites for businesses that need a credible way to launch
          and grow.
        </p>
      </div>
      <nav aria-label="Product navigation">
        <span>Product</span>
        <Link href="/website-builder">Website Builder</Link>
        <Link href="/ai-website-builder">AI Website Builder</Link>
        <Link href="/templates">Website Templates</Link>
        <Link href="/features">Features</Link>
        <Link href="/pricing">Pricing</Link>
      </nav>
      <nav aria-label="Solutions navigation">
        <span>Solutions</span>
        <Link href="/solutions/small-business">Small businesses</Link>
        <Link href="/solutions/freelancers">Freelancers</Link>
        <Link href="/blog">Journal</Link>
        <Link href="/contact">Contact</Link>
      </nav>
      <nav aria-label="Legal navigation">
        <span>Legal</span>
        <Link href="/privacy">Privacy</Link>
        <Link href="/terms">Terms</Link>
        <Link href="/cookies">Cookies</Link>
        <Link href="/refunds">Refunds</Link>
      </nav>
      <div className={styles.footerEnd}>
        <span>© 2026 Zylora</span>
        <span>Professional Websites, built your way.</span>
      </div>
    </footer>
  );
}
