'use client';

import {
  ArrowDown,
  ArrowUp,
  ChevronDown,
  ChevronRight,
  Eye,
  EyeOff,
  FileText,
  Home,
  Plus,
  Search,
  Settings2,
  Trash2,
} from 'lucide-react';
import Link from 'next/link';
import {
  type CSSProperties,
  type FormEvent,
  type KeyboardEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { Notice, StatusBadge } from '@zylora/ui';

import { apiRequest, csrfToken } from '@/lib/api';
import styles from './page-manager.module.css';

export type PageRecord = {
  id: string;
  parent_page_id: string | null;
  name: string;
  slug: string;
  path: string;
  sort_order: number;
  is_home: boolean;
  show_in_navigation: boolean;
  status: 'DRAFT' | 'HIDDEN' | 'ARCHIVED';
  seo: { title?: string; description?: string };
  created_at: string;
  updated_at: string;
};

type NavigationNode = {
  page_id: string;
  label: string;
  path: string;
  children: NavigationNode[];
};

export type WebsiteRecord = {
  id: string;
  display_name: string;
  status: string;
  revision?: number;
  pages: PageRecord[];
  navigation: NavigationNode[];
  path_changes: Array<{ page_id: string; old_path: string; new_path: string }>;
};

export type TreeRow = {
  page: PageRecord;
  depth: number;
  hasChildren: boolean;
};

type PagePatch = {
  name?: string;
  slug?: string;
  parent_page_id?: string | null;
  sort_order?: number;
  show_in_navigation?: boolean;
  status?: PageRecord['status'];
  seo?: { title: string; description: string };
};

type PageCreatePayload = {
  name: string;
  slug: string;
  parent_page_id: string | null;
  sort_order: number;
  show_in_navigation: boolean;
  status: 'DRAFT';
  seo: Record<string, string>;
};

function ordered(pages: PageRecord[]) {
  return [...pages].sort(
    (left, right) =>
      Number(right.is_home) - Number(left.is_home) ||
      left.sort_order - right.sort_order ||
      left.name.localeCompare(right.name),
  );
}

export function visibleTreeRows(
  pages: PageRecord[],
  collapsed: ReadonlySet<string>,
  query: string,
): TreeRow[] {
  const normalizedQuery = query.trim().toLowerCase();
  const childMap = new Map<string | null, PageRecord[]>();
  for (const page of pages) {
    const siblings = childMap.get(page.parent_page_id) ?? [];
    siblings.push(page);
    childMap.set(page.parent_page_id, siblings);
  }
  if (normalizedQuery) {
    return ordered(
      pages.filter(
        (page) =>
          page.name.toLowerCase().includes(normalizedQuery) ||
          page.path.toLowerCase().includes(normalizedQuery),
      ),
    ).map((page) => ({
      page,
      depth: Math.max(0, page.path.split('/').filter(Boolean).length - 1),
      hasChildren: Boolean(childMap.get(page.id)?.length),
    }));
  }
  const rows: TreeRow[] = [];
  const visit = (parentId: string | null, depth: number, branch: Set<string>) => {
    for (const page of ordered(childMap.get(parentId) ?? [])) {
      if (branch.has(page.id)) continue;
      const children = childMap.get(page.id) ?? [];
      rows.push({ page, depth, hasChildren: children.length > 0 });
      if (!collapsed.has(page.id)) visit(page.id, depth + 1, new Set([...branch, page.id]));
    }
  };
  visit(null, 0, new Set());
  return rows;
}

function descendantIds(pages: PageRecord[], pageId: string): Set<string> {
  const result = new Set<string>([pageId]);
  let changed = true;
  while (changed) {
    changed = false;
    for (const page of pages) {
      if (page.parent_page_id && result.has(page.parent_page_id) && !result.has(page.id)) {
        result.add(page.id);
        changed = true;
      }
    }
  }
  return result;
}

function mutationHeaders() {
  const token = csrfToken('zylora_user_csrf');
  return token ? { 'X-CSRF-Token': token } : {};
}

function NavigationBranch({ nodes }: { nodes: NavigationNode[] }) {
  if (nodes.length === 0) return null;
  return (
    <ul>
      {nodes.map((node) => (
        <li key={node.page_id}>
          <span>{node.label}</span>
          <small>{node.path}</small>
          <NavigationBranch nodes={node.children} />
        </li>
      ))}
    </ul>
  );
}

function AddPageForm({
  pages,
  busy,
  onCancel,
  onAdd,
}: {
  pages: PageRecord[];
  busy: boolean;
  onCancel: () => void;
  onAdd: (payload: PageCreatePayload) => Promise<void>;
}) {
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [parentId, setParentId] = useState('');
  const [visible, setVisible] = useState(true);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onAdd({
      name,
      slug,
      parent_page_id: parentId || null,
      sort_order: pages.filter((page) => page.parent_page_id === (parentId || null)).length,
      show_in_navigation: visible,
      status: 'DRAFT',
      seo: {},
    });
  }

  return (
    <form className={styles.settingsForm} onSubmit={submit}>
      <div className={styles.settingsHeading}>
        <div>
          <p>New page</p>
          <h2>Add to this Website</h2>
        </div>
        <button className={styles.quietButton} type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
      <label>
        Page name
        <input
          autoFocus
          maxLength={120}
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      <label>
        URL slug
        <span className={styles.slugField}>
          <span>/</span>
          <input
            aria-describedby="new-slug-hint"
            maxLength={120}
            pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
            required
            value={slug}
            onChange={(event) => setSlug(event.target.value)}
          />
        </span>
        <small id="new-slug-hint">Lowercase letters, numbers, and single hyphens.</small>
      </label>
      <label>
        Parent page
        <select value={parentId} onChange={(event) => setParentId(event.target.value)}>
          <option value="">Root level</option>
          {ordered(pages)
            .filter((page) => !page.is_home && page.status !== 'ARCHIVED')
            .map((page) => (
              <option key={page.id} value={page.id}>
                {page.path} ? {page.name}
              </option>
            ))}
        </select>
      </label>
      <label className={styles.checkRow}>
        <input
          checked={visible}
          type="checkbox"
          onChange={(event) => setVisible(event.target.checked)}
        />
        Show in primary navigation
      </label>
      <button className={styles.primaryButton} disabled={busy} type="submit">
        {busy ? 'Adding?' : 'Add page'}
      </button>
    </form>
  );
}

function PageSettings({
  page,
  pages,
  busy,
  onDelete,
  onSave,
}: {
  page: PageRecord;
  pages: PageRecord[];
  busy: boolean;
  onDelete: () => Promise<void>;
  onSave: (payload: PagePatch) => Promise<void>;
}) {
  const [name, setName] = useState(page.name);
  const [slug, setSlug] = useState(page.slug);
  const [parentId, setParentId] = useState(page.parent_page_id ?? '');
  const [sortOrder, setSortOrder] = useState(page.sort_order);
  const [visible, setVisible] = useState(page.show_in_navigation);
  const [status, setStatus] = useState<PageRecord['status']>(page.status);
  const [seoTitle, setSeoTitle] = useState(page.seo.title ?? '');
  const [seoDescription, setSeoDescription] = useState(page.seo.description ?? '');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const invalidParents = useMemo(() => descendantIds(pages, page.id), [page.id, pages]);
  const directChildren = pages.filter((item) => item.parent_page_id === page.id).length;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSave({
      name,
      ...(page.is_home ? {} : { slug, parent_page_id: parentId || null }),
      sort_order: sortOrder,
      show_in_navigation: visible,
      status,
      seo: { title: seoTitle, description: seoDescription },
    });
  }

  return (
    <form className={styles.settingsForm} onSubmit={submit}>
      <div className={styles.settingsHeading}>
        <div>
          <p>Page settings</p>
          <h2>{page.name}</h2>
        </div>
        <StatusBadge tone={page.is_home ? 'success' : 'neutral'}>
          {page.is_home ? 'Home page' : page.status}
        </StatusBadge>
      </div>
      <div className={styles.pathReadout}>
        <span>Canonical path</span>
        <strong>{page.path}</strong>
      </div>
      <label>
        Page name
        <input
          maxLength={120}
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      <label>
        URL slug
        <span className={styles.slugField}>
          <span>/</span>
          <input
            disabled={page.is_home}
            maxLength={120}
            pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
            required={!page.is_home}
            value={page.is_home ? '' : slug}
            onChange={(event) => setSlug(event.target.value)}
          />
        </span>
        <small>
          {page.is_home ? "Home always resolves to '/'." : 'Changing this records the old path.'}
        </small>
      </label>
      <label>
        Parent page
        <select
          disabled={page.is_home}
          value={parentId}
          onChange={(event) => setParentId(event.target.value)}
        >
          <option value="">Root level</option>
          {ordered(pages)
            .filter(
              (candidate) =>
                !candidate.is_home &&
                candidate.status !== 'ARCHIVED' &&
                !invalidParents.has(candidate.id),
            )
            .map((candidate) => (
              <option key={candidate.id} value={candidate.id}>
                {candidate.path} ? {candidate.name}
              </option>
            ))}
        </select>
      </label>
      <div className={styles.orderGroup}>
        <label>
          Navigation order
          <input
            min={0}
            type="number"
            value={sortOrder}
            onChange={(event) => setSortOrder(Number(event.target.value))}
          />
        </label>
        <div className={styles.orderButtons} aria-label="Quick reorder">
          <button
            aria-label={'Move ' + page.name + ' up'}
            disabled={busy || page.is_home || page.sort_order === 0}
            type="button"
            onClick={() => void onSave({ sort_order: Math.max(0, page.sort_order - 1) })}
          >
            <ArrowUp size={16} /> Up
          </button>
          <button
            aria-label={'Move ' + page.name + ' down'}
            disabled={busy || page.is_home}
            type="button"
            onClick={() => void onSave({ sort_order: page.sort_order + 1 })}
          >
            <ArrowDown size={16} /> Down
          </button>
        </div>
      </div>
      <label className={styles.checkRow}>
        <input
          checked={visible}
          type="checkbox"
          onChange={(event) => setVisible(event.target.checked)}
        />
        Show in primary navigation
      </label>
      <label>
        Page status
        <select
          disabled={page.is_home}
          value={status}
          onChange={(event) => setStatus(event.target.value as PageRecord['status'])}
        >
          <option value="DRAFT">Draft</option>
          <option value="HIDDEN">Hidden</option>
          <option value="ARCHIVED">Archived</option>
        </select>
      </label>
      <fieldset>
        <legend>Basic SEO entry point</legend>
        <label>
          Search title
          <input
            maxLength={70}
            value={seoTitle}
            onChange={(event) => setSeoTitle(event.target.value)}
          />
        </label>
        <label>
          Search description
          <textarea
            maxLength={180}
            rows={3}
            value={seoDescription}
            onChange={(event) => setSeoDescription(event.target.value)}
          />
        </label>
        <small>Advanced SEO controls remain a later phase.</small>
      </fieldset>
      <button className={styles.primaryButton} disabled={busy} type="submit">
        {busy ? 'Saving?' : 'Save page settings'}
      </button>
      {!page.is_home && (
        <div className={styles.dangerZone}>
          {!confirmDelete ? (
            <button
              className={styles.deleteButton}
              type="button"
              onClick={() => setConfirmDelete(true)}
            >
              <Trash2 size={16} /> Delete page
            </button>
          ) : (
            <div role="alert">
              <strong>Delete {page.name}?</strong>
              <p>
                {directChildren
                  ? `${directChildren} direct child page${directChildren === 1 ? '' : 's'} will move up one level. No descendants will be deleted.`
                  : 'This page has no children. Only this page will be deleted.'}
              </p>
              <div>
                <button
                  className={styles.quietButton}
                  type="button"
                  onClick={() => setConfirmDelete(false)}
                >
                  Keep page
                </button>
                <button
                  className={styles.deleteButton}
                  disabled={busy}
                  type="button"
                  onClick={() => void onDelete()}
                >
                  Confirm delete
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </form>
  );
}

export function PageManager({ websiteId }: { websiteId: string }) {
  const [website, setWebsite] = useState<WebsiteRecord | null>(null);
  const [selectedId, setSelectedId] = useState('');
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState('');
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const rowRefs = useRef(new Map<string, HTMLButtonElement>());

  useEffect(() => {
    let active = true;
    apiRequest<WebsiteRecord>(`/api/v1/websites/${websiteId}`)
      .then((result) => {
        if (!active) return;
        setWebsite(result);
        setSelectedId(result.pages.find((page) => page.is_home)?.id ?? result.pages[0]?.id ?? '');
      })
      .catch((reason) => {
        if (active)
          setError(reason instanceof Error ? reason.message : 'Page Manager is unavailable.');
      });
    return () => {
      active = false;
    };
  }, [websiteId]);

  const rows = useMemo(
    () => visibleTreeRows(website?.pages ?? [], collapsed, query),
    [collapsed, query, website?.pages],
  );
  const selected = website?.pages.find((page) => page.id === selectedId) ?? null;

  function mutationMessage(result: WebsiteRecord, fallback: string) {
    if (!result.path_changes.length) return fallback;
    const first = result.path_changes[0]!;
    const more = result.path_changes.length - 1;
    return `Path updated: ${first.old_path} ? ${first.new_path}${more ? ` and ${more} descendant${more === 1 ? '' : 's'}` : ''}. Redirect history was recorded.`;
  }

  async function mutate(
    path: string,
    method: 'POST' | 'PATCH' | 'DELETE',
    body: object,
    fallback: string,
  ) {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const result = await apiRequest<WebsiteRecord>(path, {
        method,
        body: JSON.stringify(body),
        headers: mutationHeaders(),
      });
      setWebsite(result);
      setMessage(mutationMessage(result, fallback));
      return result;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The Page change could not be saved.');
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function addPage(payload: PageCreatePayload) {
    const result = await mutate(
      `/api/v1/websites/${websiteId}/pages`,
      'POST',
      payload,
      'Page added to this Draft.',
    );
    if (!result) return;
    const created = result.pages.find(
      (page) => page.name === payload.name && page.slug === payload.slug,
    );
    if (created) setSelectedId(created.id);
    setAdding(false);
  }

  async function savePage(payload: PagePatch) {
    if (!selected) return;
    await mutate(
      `/api/v1/websites/${websiteId}/pages/${selected.id}`,
      'PATCH',
      payload,
      'Page settings saved. Navigation was regenerated.',
    );
  }

  async function deletePage() {
    if (!selected) return;
    const result = await mutate(
      `/api/v1/websites/${websiteId}/pages/${selected.id}`,
      'DELETE',
      { confirm: true, child_strategy: 'PROMOTE' },
      'Page deleted. Its direct children moved up one level.',
    );
    if (result) setSelectedId(result.pages.find((page) => page.is_home)?.id ?? '');
  }

  function toggle(pageId: string) {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(pageId)) next.delete(pageId);
      else next.add(pageId);
      return next;
    });
  }

  function treeKeyDown(event: KeyboardEvent<HTMLButtonElement>, row: TreeRow, index: number) {
    const focus = (target: TreeRow | undefined) =>
      target && rowRefs.current.get(target.page.id)?.focus();
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      focus(rows[index + 1]);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      focus(rows[index - 1]);
    } else if (event.key === 'Home') {
      event.preventDefault();
      focus(rows[0]);
    } else if (event.key === 'End') {
      event.preventDefault();
      focus(rows.at(-1));
    } else if (event.key === 'ArrowRight' && row.hasChildren) {
      event.preventDefault();
      if (collapsed.has(row.page.id)) toggle(row.page.id);
      else focus(rows[index + 1]);
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault();
      if (row.hasChildren && !collapsed.has(row.page.id)) toggle(row.page.id);
      else focus(rows.find((candidate) => candidate.page.id === row.page.parent_page_id));
    }
  }

  if (error && !website) {
    return (
      <Notice tone="danger" title="Page Manager unavailable">
        {error}
      </Notice>
    );
  }
  if (!website) return <p role="status">Loading Website pages?</p>;

  return (
    <div className={styles.editor}>
      <header className={styles.editorHeader}>
        <div>
          <Link href="/app/websites">? All Websites</Link>
          <p>Draft Website</p>
          <h1>{website.display_name}</h1>
        </div>
        <div className={styles.editorMeta}>
          <StatusBadge tone="info">{website.status}</StatusBadge>
          <span>{website.pages.length} pages</span>
          <span>No plan required</span>
        </div>
      </header>

      {(message || error) && (
        <div className={error ? styles.feedbackError : styles.feedback} role="status">
          {error || message}
        </div>
      )}

      <div className={styles.editorGrid}>
        <section className={styles.treePanel} aria-labelledby="pages-heading">
          <div className={styles.panelHeading}>
            <div>
              <p>Website map</p>
              <h2 id="pages-heading">Pages</h2>
            </div>
            <button className={styles.addButton} type="button" onClick={() => setAdding(true)}>
              <Plus size={17} /> Add page
            </button>
          </div>
          <label className={styles.search}>
            <Search size={17} />
            <span className="sr-only">Search pages</span>
            <input
              placeholder="Search pages or paths"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <p className={styles.resultCount} aria-live="polite">
            {rows.length} of {website.pages.length} pages
          </p>
          <div className={styles.treeScroll}>
            <div aria-label="Website page hierarchy" role="tree">
              {rows.map((row, index) => (
                <div
                  aria-expanded={row.hasChildren ? !collapsed.has(row.page.id) : undefined}
                  aria-level={row.depth + 1}
                  aria-selected={selectedId === row.page.id}
                  className={selectedId === row.page.id ? styles.treeRowActive : styles.treeRow}
                  key={row.page.id}
                  role="treeitem"
                  style={{ '--tree-depth': row.depth } as CSSProperties}
                >
                  {row.hasChildren ? (
                    <button
                      aria-label={
                        (collapsed.has(row.page.id) ? 'Expand ' : 'Collapse ') + row.page.name
                      }
                      className={styles.expandButton}
                      type="button"
                      onClick={() => toggle(row.page.id)}
                    >
                      {collapsed.has(row.page.id) ? (
                        <ChevronRight size={16} />
                      ) : (
                        <ChevronDown size={16} />
                      )}
                    </button>
                  ) : (
                    <span className={styles.expandSpacer} />
                  )}
                  <button
                    className={styles.pageButton}
                    aria-label={'Open ' + row.page.name}
                    ref={(element) => {
                      if (element) rowRefs.current.set(row.page.id, element);
                      else rowRefs.current.delete(row.page.id);
                    }}
                    type="button"
                    onClick={() => {
                      setSelectedId(row.page.id);
                      setAdding(false);
                    }}
                    onKeyDown={(event) => treeKeyDown(event, row, index)}
                  >
                    {row.page.is_home ? <Home size={16} /> : <FileText size={16} />}
                    <span>
                      <strong>{row.page.name}</strong>
                      <small>{row.page.path}</small>
                    </span>
                    {row.page.show_in_navigation ? (
                      <Eye aria-label="Shown in navigation" size={15} />
                    ) : (
                      <EyeOff aria-label="Hidden from navigation" size={15} />
                    )}
                  </button>
                </div>
              ))}
            </div>
          </div>
          <p className={styles.keyboardHint}>
            Use ?/? to move, ?/? to collapse or enter groups, and Enter to select.
          </p>
        </section>

        <section className={styles.settingsPanel} aria-label="Selected Page settings">
          {adding ? (
            <AddPageForm
              pages={website.pages}
              busy={busy}
              onAdd={addPage}
              onCancel={() => setAdding(false)}
            />
          ) : selected ? (
            <PageSettings
              key={`${selected.id}:${selected.updated_at}`}
              page={selected}
              pages={website.pages}
              busy={busy}
              onDelete={deletePage}
              onSave={savePage}
            />
          ) : (
            <div className={styles.noSelection}>
              <Settings2 size={24} />
              <h2>Select a page</h2>
              <p>Choose a compact row to open its Page settings.</p>
            </div>
          )}
        </section>

        <aside className={styles.navigationPanel} aria-labelledby="navigation-heading">
          <p>Generated automatically</p>
          <h2 id="navigation-heading">Primary navigation</h2>
          <p className={styles.navigationHelp}>
            Only navigation-visible pages appear here. Hidden pages still exist at their canonical
            URLs.
          </p>
          {website.navigation.length ? (
            <nav aria-label="Generated Website navigation">
              <NavigationBranch nodes={website.navigation} />
            </nav>
          ) : (
            <p>No pages are currently visible in primary navigation.</p>
          )}
        </aside>
      </div>
    </div>
  );
}
