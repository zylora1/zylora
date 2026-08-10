'use client';

import Script from 'next/script';
import { useEffect, useRef, useState } from 'react';

import { apiRequest } from '@/lib/api';

export type TurnstileAction =
  'signup' | 'login' | 'verify_email' | 'password_recovery' | 'admin_login' | 'contact';

type ChallengeConfig = { enabled: boolean; site_key: string | null };
type WidgetId = string;
type TurnstileApi = {
  render: (container: HTMLElement, options: Record<string, unknown>) => WidgetId;
  remove: (widgetId: WidgetId) => void;
};

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

export function TurnstileWidget({
  action,
  resetKey,
  onToken,
  onRequirementChange,
  onError,
}: {
  action: TurnstileAction;
  resetKey: number;
  onToken: (token: string | null) => void;
  onRequirementChange: (required: boolean) => void;
  onError: (message: string) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const widgetId = useRef<WidgetId | null>(null);
  const [config, setConfig] = useState<ChallengeConfig | null>(null);
  const [scriptReady, setScriptReady] = useState(false);

  useEffect(() => {
    let active = true;
    apiRequest<ChallengeConfig>('/api/v1/auth/challenge/config')
      .then((next) => {
        if (!active) return;
        setConfig(next);
        onRequirementChange(next.enabled);
        if (!next.enabled) onToken(null);
        else if (!next.site_key) onError('Security verification is unavailable.');
      })
      .catch(() => {
        if (!active) return;
        onRequirementChange(true);
        onError('Security verification is unavailable.');
      });
    return () => {
      active = false;
    };
  }, [onError, onRequirementChange, onToken]);

  useEffect(() => {
    if (!config?.enabled || !config.site_key || !scriptReady || !container.current) return;
    const turnstile = window.turnstile;
    if (!turnstile) {
      onError('Security verification is unavailable.');
      return;
    }
    if (widgetId.current) turnstile.remove(widgetId.current);
    onToken(null);
    widgetId.current = turnstile.render(container.current, {
      sitekey: config.site_key,
      action,
      appearance: 'interaction-only',
      execution: 'render',
      size: 'flexible',
      theme: 'light',
      callback: (token: string) => onToken(token),
      'expired-callback': () => onToken(null),
      'timeout-callback': () => onToken(null),
      'error-callback': () => {
        onToken(null);
        onError('Security verification failed. Please try again.');
        return true;
      },
    });
    return () => {
      if (widgetId.current) turnstile.remove(widgetId.current);
      widgetId.current = null;
    };
  }, [action, config, onError, onToken, resetKey, scriptReady]);

  if (!config?.enabled) return null;
  return (
    <div className="turnstile-shell" aria-label="Security verification">
      <Script
        id="cloudflare-turnstile"
        src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit"
        strategy="afterInteractive"
        onLoad={() => setScriptReady(true)}
        onError={() => onError('Security verification is unavailable.')}
      />
      <div ref={container} />
    </div>
  );
}
