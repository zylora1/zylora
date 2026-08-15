import { afterEach, describe, expect, it } from 'vitest';

import { captureAttribution, currentAttribution } from './attribution';

afterEach(() => {
  sessionStorage.clear();
  window.history.replaceState({}, '', '/');
});

describe('first-touch acquisition attribution', () => {
  it('captures bounded UTM/referrer context once for the current session', () => {
    window.history.replaceState(
      {},
      '',
      '/signup?utm_source=instagram&utm_medium=social&utm_campaign=launch',
    );
    captureAttribution();
    expect(currentAttribution()).toMatchObject({
      utm_source: 'instagram',
      utm_medium: 'social',
      utm_campaign: 'launch',
      landing_page: '/signup?utm_source=instagram&utm_medium=social&utm_campaign=launch',
    });

    window.history.replaceState({}, '', '/signup?utm_source=linkedin');
    captureAttribution();
    expect(currentAttribution()?.utm_source).toBe('instagram');
  });

  it('does not create a visitor identity or store precise location', () => {
    captureAttribution();
    const raw = sessionStorage.getItem('zylora.acquisition.first-touch') ?? '';
    expect(raw).not.toContain('visitor');
    expect(raw).not.toContain('latitude');
    expect(raw).not.toContain('longitude');
  });
});
