import type { TemplateDocument } from '@zylora/template-schema';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { documentPageDatabaseId, type EditorState, WebsiteEditor } from './website-editor';

const pageUuid = '12345678-1234-4567-89ab-1234567890ab';

function document(): TemplateDocument {
  return {
    schema_version: '1.0.0',
    registry_version: '1.0.0',
    metadata: { name: 'Editor Draft', description: 'Editor test.', language: 'en' },
    theme: {
      primary: '#5B5BD6',
      accent: '#27C499',
      surface: '#FFFFFF',
      ink: '#171A2B',
      heading_font: 'MANROPE',
      body_font: 'INTER',
    },
    assets: [],
    pages: [
      {
        id: `p${pageUuid.replaceAll('-', '')}`,
        slug: 'home',
        label: 'Home',
        parent_page_id: null,
        sort_order: 0,
        is_home: true,
        show_in_navigation: true,
        status: 'ACTIVE',
        seo: { title: 'Home', description: 'Welcome home.' },
        components: [
          {
            id: 'hero-home',
            type: 'HERO',
            props: { heading: 'A thoughtful first impression', body: 'A clear introduction.' },
            children: [],
            responsive: {},
            interactions: [],
          },
        ],
      },
    ],
    features: [],
    requirements: [],
    provenance: 'CURATED',
  };
}

function editorState(): EditorState {
  return {
    website_id: 'website-1',
    display_name: 'Premium Studio Draft',
    status: 'DRAFT',
    revision: 1,
    document: document(),
    revisions: [
      {
        id: 'revision-1',
        revision: 1,
        source: 'TEMPLATE',
        edit_summary: 'Created from template',
        created_at: '2026-08-12T00:00:00Z',
      },
    ],
    credits: {
      balance: 15,
      allowance: 15,
      period_start: '2026-08-01T00:00:00Z',
      period_end: '2026-09-01T00:00:00Z',
    },
  };
}

function response(body: object) {
  return Promise.resolve({ ok: true, status: 200, json: async () => body });
}

afterEach(() => vi.unstubAllGlobals());

describe('Website editor', () => {
  it('maps immutable document page IDs back to Website Page IDs', () => {
    expect(documentPageDatabaseId(`p${pageUuid.replaceAll('-', '')}`)).toBe(pageUuid);
    expect(documentPageDatabaseId('not-a-page-id')).toBe('');
  });

  it('autosaves supported component fields and applies page-graph-aware AI prompts', async () => {
    let state = editorState();
    const fetcher = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const path = String(input);
      if (!init?.method) return response(state);
      const payload = JSON.parse(String(init.body)) as {
        prompt?: string;
        scope: string;
        selected_page_id?: string;
        operations?: Array<Record<string, unknown>>;
      };
      state = {
        ...state,
        revision: state.revision + 1,
        credits: {
          ...state.credits,
          balance: path.endsWith('/ai-edits') ? state.credits.balance - 1 : state.credits.balance,
        },
        revisions: [
          {
            id: `revision-${state.revision + 1}`,
            revision: state.revision + 1,
            source: path.endsWith('/ai-edits') ? 'AI' : 'MANUAL',
            edit_summary: path.endsWith('/ai-edits') ? 'AI changed the Website' : 'Heading saved',
            created_at: '2026-08-12T00:01:00Z',
          },
          ...state.revisions,
        ],
      };
      return response({
        ...state,
        operation_id: 'operation-1',
        source: path.endsWith('/ai-edits') ? 'AI' : 'MANUAL',
        summary: path.endsWith('/ai-edits') ? 'AI changed the Website' : 'Heading saved',
        credits_used: path.endsWith('/ai-edits') ? 1 : 0,
        _payload: payload,
      });
    });
    vi.stubGlobal('fetch', fetcher);

    render(<WebsiteEditor websiteId="website-1" />);
    fireEvent.click(screen.getByRole('button', { name: 'Content & AI' }));
    expect(await screen.findByRole('heading', { name: 'Premium Studio Draft' })).toBeVisible();
    expect(screen.getByText('15 AI credits')).toBeVisible();

    const heading = screen.getByLabelText('heading');
    fireEvent.change(heading, { target: { value: 'A sharper first impression' } });
    fireEvent.blur(heading);
    await waitFor(() =>
      expect(fetcher).toHaveBeenCalledWith(
        '/api/v1/websites/website-1/editor/edits',
        expect.objectContaining({ method: 'POST' }),
      ),
    );
    const manual = JSON.parse(String(fetcher.mock.calls.at(-1)?.[1]?.body)) as {
      base_revision: number;
      selected_page_id: string;
      operations: Array<{ kind: string; page_id: string }>;
    };
    expect(manual).toMatchObject({ base_revision: 1, selected_page_id: pageUuid });
    expect(manual.operations[0]).toMatchObject({ kind: 'SET_COMPONENT_PROP', page_id: pageUuid });

    fireEvent.change(screen.getByLabelText('Change scope'), { target: { value: 'WEBSITE' } });
    fireEvent.change(screen.getByLabelText('Tell Zylora what to change'), {
      target: { value: 'Add an FAQ page under Resources and show it in navigation.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Plan and apply change' }));
    await waitFor(() =>
      expect(fetcher).toHaveBeenCalledWith(
        '/api/v1/websites/website-1/editor/ai-edits',
        expect.objectContaining({ method: 'POST' }),
      ),
    );
    const ai = JSON.parse(String(fetcher.mock.calls.at(-1)?.[1]?.body)) as {
      base_revision: number;
      scope: string;
      selected_page_id: string | null;
    };
    expect(ai).toMatchObject({ base_revision: 2, scope: 'WEBSITE', selected_page_id: null });
    expect(await screen.findByText(/1 credit used/)).toBeVisible();
  });
});
