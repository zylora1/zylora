'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useState } from 'react';
import { Button, Notice, StatusBadge } from '@zylora/ui';

import { apiRequest, csrfToken } from '@/lib/api';
import styles from './template-platform.module.css';

type Version = {
  id: string;
  version: number;
  status: string;
  checksum: string;
  validation_summary: Record<string, unknown> | null;
  created_at: string;
};
type AdminTemplate = {
  id: string;
  slug: string;
  name: string;
  summary: string;
  status: string;
  category: string;
  tags: string[];
  versions: Version[];
};
type Response = { items: AdminTemplate[] };

export function TemplateManagement() {
  const [items, setItems] = useState<AdminTemplate[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [documents, setDocuments] = useState<Record<string, string>>({});
  const headers = () => ({ 'X-CSRF-Token': csrfToken('zylora_admin_csrf') ?? '' });
  const load = async () => {
    try {
      setItems((await apiRequest<Response>('/api/v1/admin/templates')).items);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Template management is unavailable.');
    }
  };
  useEffect(() => {
    void Promise.resolve().then(() => load());
  }, []);
  const create = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      await apiRequest('/api/v1/admin/templates', {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({
          slug: data.get('slug'),
          name: data.get('name'),
          summary: data.get('summary'),
          category_slug: data.get('categorySlug'),
          category_name: data.get('categoryName'),
          category_description: data.get('categoryDescription'),
          tags: String(data.get('tags') ?? '')
            .split(',')
            .map((value) => value.trim())
            .filter(Boolean),
          featured_order: Number(data.get('featuredOrder') || 1000),
        }),
      });
      event.currentTarget.reset();
      setNotice('Template identity created. Add an immutable document version next.');
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Template creation failed.');
    }
  };
  const updateMetadata = async (template: AdminTemplate) => {
    const name = window.prompt('Template name', template.name);
    if (name === null) return;
    const summary = window.prompt('Template summary', template.summary);
    if (summary === null) return;
    const categorySlug = window.prompt(
      'Category slug (leave blank to keep the current category)',
      '',
    );
    const categoryName = categorySlug ? window.prompt('New category name') : null;
    const categoryDescription = categorySlug ? window.prompt('New category description') : null;
    const tags = window.prompt('Tags, comma separated', template.tags.join(', '));
    const featuredOrder = window.prompt('Featured order (leave blank to keep current)', '');
    try {
      await apiRequest(`/api/v1/admin/templates/${template.id}`, {
        method: 'PATCH',
        headers: headers(),
        body: JSON.stringify({
          name,
          summary,
          ...(categorySlug && categoryName && categoryDescription
            ? {
                category_slug: categorySlug,
                category_name: categoryName,
                category_description: categoryDescription,
              }
            : {}),
          ...(tags === null
            ? {}
            : {
                tags: tags
                  .split(',')
                  .map((value) => value.trim())
                  .filter(Boolean),
              }),
          ...(featuredOrder ? { featured_order: Number(featuredOrder) } : {}),
        }),
      });
      setNotice('Template metadata was updated through the audited catalog service.');
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Template metadata update failed.');
    }
  };
  const addVersion = async (templateId: string) => {
    try {
      const document = JSON.parse(documents[templateId] ?? '');
      await apiRequest(`/api/v1/admin/templates/${templateId}/versions`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ document }),
      });
      setNotice('Draft version created. Validate it before approval.');
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The document is not valid JSON.');
    }
  };
  const transition = async (templateId: string, version: number, action: string) => {
    const reason = window.prompt(`Reason for ${action} (minimum 8 characters)`);
    if (!reason) return;
    try {
      await apiRequest(`/api/v1/admin/templates/${templateId}/versions/${version}/${action}`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ reason }),
      });
      setNotice(`Version ${version} moved through ${action}.`);
      await load();
    } catch (reasonValue) {
      setError(reasonValue instanceof Error ? reasonValue.message : `Could not ${action}.`);
    }
  };
  return (
    <div className={styles.adminStack}>
      {error ? (
        <Notice tone="danger" title="Template command failed">
          {error}
        </Notice>
      ) : null}
      {notice ? (
        <Notice tone="success" title="Template platform updated">
          {notice}
        </Notice>
      ) : null}
      <form className={styles.adminForm} onSubmit={create}>
        <label>
          Name
          <input name="name" required maxLength={120} />
        </label>
        <label>
          Slug
          <input name="slug" required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" />
        </label>
        <label className={styles.wide}>
          Summary
          <textarea name="summary" required maxLength={500} />
        </label>
        <label>
          Category name
          <input name="categoryName" required />
        </label>
        <label>
          Category slug
          <input name="categorySlug" required />
        </label>
        <label className={styles.wide}>
          Category description
          <input name="categoryDescription" required />
        </label>
        <label>
          Tags, comma separated
          <input name="tags" />
        </label>
        <label>
          Featured order
          <input name="featuredOrder" type="number" defaultValue="1000" min="0" max="10000" />
        </label>
        <button className={styles.wide} type="submit">
          Create Template identity
        </button>
      </form>
      {items.length === 0 ? (
        <div className={styles.empty}>
          No Template identities exist yet. Create one above or run the curated catalogue seed.
        </div>
      ) : (
        items.map((template) => (
          <article className={styles.adminTemplate} key={template.id}>
            <header>
              <div>
                <h2>{template.name}</h2>
                <p>{template.summary}</p>
              </div>
              <StatusBadge tone={template.status === 'ACTIVE' ? 'success' : 'neutral'}>
                {template.status}
              </StatusBadge>
            </header>
            <label className={styles.wide}>
              New structured document JSON
              <textarea
                value={documents[template.id] ?? ''}
                onChange={(event) =>
                  setDocuments((current) => ({ ...current, [template.id]: event.target.value }))
                }
                rows={7}
              />
            </label>
            <div className={styles.versionActions}>
              <Button variant="secondary" onClick={() => void addVersion(template.id)}>
                Add immutable version
              </Button>
              <button type="button" onClick={() => void updateMetadata(template)}>
                Edit metadata
              </button>
            </div>
            {template.versions.map((version) => (
              <div className={styles.versionRow} key={version.id}>
                <strong>v{version.version}</strong>
                <StatusBadge
                  tone={
                    version.status === 'PUBLISHED'
                      ? 'success'
                      : version.status === 'REJECTED'
                        ? 'danger'
                        : 'info'
                  }
                >
                  {version.status}
                </StatusBadge>
                <div className={styles.versionActions}>
                  {version.status === 'PUBLISHED' ? (
                    <Link href={`/templates/${template.slug}/preview?version=${version.version}`}>
                      Preview
                    </Link>
                  ) : null}
                  {['validate', 'approve', 'publish', 'unpublish', 'deprecate', 'restore'].map(
                    (action) => (
                      <button
                        type="button"
                        key={action}
                        onClick={() => void transition(template.id, version.version, action)}
                      >
                        {action}
                      </button>
                    ),
                  )}
                </div>
              </div>
            ))}
          </article>
        ))
      )}
    </div>
  );
}
