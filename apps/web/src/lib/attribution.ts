'use client';

export type AcquisitionAttribution = {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  utm_term?: string;
  referrer?: string;
  landing_page?: string;
};

const KEY = 'zylora.acquisition.first-touch';
const FIELDS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'] as const;

function bounded(value: string | null, limit: number): string | undefined {
  const candidate = value?.trim();
  return candidate ? candidate.slice(0, limit) : undefined;
}

export function captureAttribution(): void {
  try {
    if (sessionStorage.getItem(KEY)) return;
    const search = new URLSearchParams(window.location.search);
    const attribution: AcquisitionAttribution = {};
    const referrer = bounded(document.referrer, 1000);
    const landingPage = bounded(`${window.location.pathname}${window.location.search}`, 1000);
    if (referrer) attribution.referrer = referrer;
    if (landingPage) attribution.landing_page = landingPage;
    for (const field of FIELDS) {
      const value = bounded(
        search.get(field),
        field === 'utm_source' || field === 'utm_medium' ? 160 : 200,
      );
      if (value) attribution[field] = value;
    }
    sessionStorage.setItem(KEY, JSON.stringify(attribution));
  } catch {
    // Attribution is optional and must never block navigation or authentication.
  }
}

export function currentAttribution(): AcquisitionAttribution | undefined {
  try {
    captureAttribution();
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return undefined;
    const parsed: unknown = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? (parsed as AcquisitionAttribution) : undefined;
  } catch {
    return undefined;
  }
}
