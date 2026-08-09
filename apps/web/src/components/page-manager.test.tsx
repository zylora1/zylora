import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { PageManager, type PageRecord, type WebsiteRecord, visibleTreeRows } from './page-manager';

function makeWebsite(count: number): WebsiteRecord {
  const now = '2026-08-11T00:00:00Z';
  const pages: PageRecord[] = Array.from({ length: count }, (_, index) => {
    const isHome = index === 0;
    const groupRoot = index ? index - ((index - 1) % 10) : 0;
    const parentIndex = isHome || index % 10 === 1 ? null : groupRoot;
    const parentPath = parentIndex ? `/page-${parentIndex}` : '';
    return {
      id: `page-${index}`,
      parent_page_id: parentIndex ? `page-${parentIndex}` : null,
      name: isHome ? 'Home' : `Page ${index}`,
      slug: isHome ? '' : `page-${index}`,
      path: isHome ? '/' : `${parentPath}/page-${index}`,
      sort_order: index % 10,
      is_home: isHome,
      show_in_navigation: index % 6 !== 0,
      status: 'DRAFT',
      seo: {},
      created_at: now,
      updated_at: now,
    };
  });
  return {
    id: 'website-1',
    display_name: 'Hundred Page Draft',
    status: 'DRAFT',
    pages,
    navigation: pages
      .filter((page) => page.parent_page_id === null && page.show_in_navigation)
      .map((page) => ({
        page_id: page.id,
        label: page.name,
        path: page.path,
        children: [],
      })),
    path_changes: [],
  };
}

function response(body: WebsiteRecord, status = 200) {
  return Promise.resolve({
    ok: status < 400,
    status,
    json: async () => body,
  });
}

afterEach(() => vi.unstubAllGlobals());

describe('Page Manager', () => {
  it.each([1, 5, 30, 100])('builds a compact searchable tree for %i pages', (count) => {
    const website = makeWebsite(count);
    expect(visibleTreeRows(website.pages, new Set(), '')).toHaveLength(count);
    if (count === 100) {
      expect(visibleTreeRows(website.pages, new Set(['page-1']), '')).toHaveLength(91);
      const matches = visibleTreeRows(website.pages, new Set(), 'page-99');
      expect(matches.map((row) => row.page.name)).toEqual(['Page 99']);
    }
  });

  it('supports collapse, keyboard selection, settings, add, navigation visibility, and safe delete', async () => {
    let website = makeWebsite(30);
    const fetcher = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const method = init?.method ?? 'GET';
      const path = String(input);
      if (method === 'PATCH') {
        const patch = JSON.parse(String(init?.body)) as Partial<PageRecord>;
        const pageId = path.split('/').at(-1);
        website = {
          ...website,
          pages: website.pages.map((page) =>
            page.id === pageId
              ? {
                  ...page,
                  ...patch,
                  seo: patch.seo ?? page.seo,
                  updated_at: '2026-08-11T00:01:00Z',
                }
              : page,
          ),
          path_changes: [],
        };
      } else if (method === 'POST') {
        const payload = JSON.parse(String(init?.body)) as {
          name: string;
          slug: string;
          parent_page_id: string | null;
          show_in_navigation: boolean;
        };
        website = {
          ...website,
          pages: [
            ...website.pages,
            {
              id: 'new-page',
              ...payload,
              path: `/${payload.slug}`,
              sort_order: 99,
              is_home: false,
              status: 'DRAFT',
              seo: {},
              created_at: '2026-08-11T00:01:00Z',
              updated_at: '2026-08-11T00:01:00Z',
            },
          ],
          path_changes: [],
        };
      } else if (method === 'DELETE') {
        const pageId = path.split('/').at(-1);
        website = {
          ...website,
          pages: website.pages.filter((page) => page.id !== pageId),
          path_changes: [],
        };
      }
      return response(website);
    });
    vi.stubGlobal('fetch', fetcher);

    render(<PageManager websiteId="website-1" />);
    expect(await screen.findByRole('heading', { name: 'Hundred Page Draft' })).toBeInTheDocument();
    expect(screen.getByText('30 pages')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Collapse Page 1' }));
    expect(screen.queryByRole('button', { name: 'Open Page 2' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Expand Page 1' }));
    const pageTwo = screen.getByRole('button', { name: 'Open Page 2' });
    pageTwo.focus();
    fireEvent.keyDown(pageTwo, { key: 'ArrowDown' });
    expect(screen.getByRole('button', { name: 'Open Page 3' })).toHaveFocus();
    fireEvent.click(pageTwo);

    fireEvent.change(screen.getByLabelText('Page name'), { target: { value: 'SEO Services' } });
    fireEvent.click(screen.getByLabelText('Show in primary navigation'));
    fireEvent.click(screen.getByRole('button', { name: 'Save page settings' }));
    await waitFor(() =>
      expect(fetcher).toHaveBeenCalledWith(
        '/api/v1/websites/website-1/pages/page-2',
        expect.objectContaining({ method: 'PATCH' }),
      ),
    );
    const patchBody = JSON.parse(String(fetcher.mock.calls.at(-1)?.[1]?.body)) as {
      name: string;
      show_in_navigation: boolean;
    };
    expect(patchBody).toMatchObject({ name: 'SEO Services', show_in_navigation: false });

    fireEvent.click(screen.getByRole('button', { name: 'Add page' }));
    fireEvent.change(screen.getByLabelText('Page name'), { target: { value: 'Campaign' } });
    fireEvent.change(screen.getByLabelText(/URL slug/), { target: { value: 'campaign' } });
    const addForm = screen.getByRole('heading', { name: 'Add to this Website' }).closest('form');
    fireEvent.click(within(addForm!).getByRole('button', { name: 'Add page' }));
    expect(await screen.findByRole('heading', { name: 'Campaign' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Delete page' }));
    expect(
      screen.getByText('This page has no children. Only this page will be deleted.'),
    ).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Confirm delete' }));
    await waitFor(() =>
      expect(fetcher).toHaveBeenCalledWith(
        '/api/v1/websites/website-1/pages/new-page',
        expect.objectContaining({
          method: 'DELETE',
          body: JSON.stringify({ confirm: true, child_strategy: 'PROMOTE' }),
        }),
      ),
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open Home' }));
    expect(screen.getByLabelText(/URL slug/)).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Delete page' })).not.toBeInTheDocument();
  }, 15_000);
});
