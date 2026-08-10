'use client';

import { FormEvent, useEffect, useState } from 'react';
import { Notice, StatusBadge } from '@zylora/ui';

import { apiRequest, csrfToken } from '@/lib/api';

type Campaign = {
  id: string;
  name: string;
  subject: string;
  state: string;
  audience_type: string;
  audience_snapshot_count: number;
  scheduled_at: string | null;
  accepted_count: number;
  failed_count: number;
  suppressed_count: number;
  unsubscribed_count: number;
};
type BlogPost = {
  id: string;
  title: string;
  slug: string;
  state: string;
  excerpt: string;
  published_at: string | null;
  categories: string[];
  tags: string[];
};

const headers = () => ({ 'X-CSRF-Token': csrfToken('zylora_admin_csrf') ?? '' });

export function ContentOperations() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [posts, setPosts] = useState<BlogPost[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const load = async () => {
    try {
      const [nextCampaigns, nextPosts] = await Promise.all([
        apiRequest<Campaign[]>('/api/v1/admin/campaigns'),
        apiRequest<BlogPost[]>('/api/v1/admin/blog/posts'),
      ]);
      setCampaigns(nextCampaigns);
      setPosts(nextPosts);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Content operations are unavailable.');
    }
  };
  useEffect(() => {
    if (!csrfToken('zylora_admin_csrf')) return undefined;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, []);
  const command = async (url: string, body: object) => {
    try {
      await apiRequest(url, { method: 'POST', headers: headers(), body: JSON.stringify(body) });
      setNotice('The operation was accepted and audited.');
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The operation could not be completed.');
    }
  };
  const createCampaign = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      await apiRequest('/api/v1/admin/campaigns', {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({
          name: data.get('name'),
          subject: data.get('subject'),
          body: data.get('body'),
          audience_type: data.get('audience_type'),
          audience_plan_code: null,
        }),
      });
      event.currentTarget.reset();
      setNotice('Draft campaign created. Prepare it before sending.');
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Campaign draft could not be created.');
    }
  };
  const createPost = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      await apiRequest('/api/v1/admin/blog/posts', {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({
          title: data.get('title'),
          slug: data.get('slug'),
          excerpt: data.get('excerpt'),
          content: data.get('content'),
          categories: [],
          tags: [],
        }),
      });
      event.currentTarget.reset();
      setNotice('Blog draft created. Prepare it before publishing.');
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Blog draft could not be created.');
    }
  };
  return (
    <div className="admin-operations content-operations">
      {error ? (
        <Notice tone="danger" title="Content operation unavailable">
          {error}
        </Notice>
      ) : null}
      {notice ? (
        <Notice tone="success" title="Recorded">
          {notice}
        </Notice>
      ) : null}
      <section>
        <div className="admin-operations__summary">
          <div>
            <p className="workspace-kicker">Campaigns</p>
            <h2>Server-resolved audiences</h2>
            <p>
              Recipients remain private, are snapshotted at send time, and rechecked for suppression
              at delivery.
            </p>
          </div>
          <StatusBadge tone="info">Marketing only</StatusBadge>
        </div>
        <form className="content-operations__form" onSubmit={createCampaign}>
          <label>
            Name
            <input name="name" required maxLength={160} />
          </label>
          <label>
            Subject
            <input name="subject" required maxLength={200} />
          </label>
          <label>
            Audience
            <select name="audience_type" defaultValue="ALL_USERS">
              <option value="ALL_USERS">All active users</option>
              <option value="FREE_USERS">Free users</option>
              <option value="PAID_USERS">Paid users</option>
              <option value="RECENT_USERS">Recent users</option>
              <option value="HAS_DRAFT">Has Draft</option>
              <option value="NO_PUBLISHED_WEBSITE">No published Website</option>
            </select>
          </label>
          <label className="content-operations__wide">
            Plain-text body
            <textarea name="body" required maxLength={20000} />
          </label>
          <button type="submit">Create campaign draft</button>
        </form>
        <div className="content-operations__rows">
          {campaigns.map((campaign) => (
            <article key={campaign.id}>
              <div>
                <strong>{campaign.name}</strong>
                <span>
                  {campaign.subject} / {campaign.audience_type} / {campaign.audience_snapshot_count}{' '}
                  recipients / {campaign.accepted_count} provider accepted / {campaign.failed_count}{' '}
                  failed / {campaign.suppressed_count + campaign.unsubscribed_count} suppressed
                </span>
              </div>
              <StatusBadge tone="neutral">{campaign.state}</StatusBadge>
              <div className="content-operations__actions">
                {campaign.state === 'DRAFT' ? (
                  <button
                    type="button"
                    onClick={() =>
                      void command(`/api/v1/admin/campaigns/${campaign.id}/ready`, {
                        reason: 'Content reviewed.',
                      })
                    }
                  >
                    Prepare
                  </button>
                ) : null}
                {['READY', 'SCHEDULED'].includes(campaign.state) ? (
                  <button
                    type="button"
                    onClick={() =>
                      void command(`/api/v1/admin/campaigns/${campaign.id}/send`, {
                        reason: 'Authorized send.',
                      })
                    }
                  >
                    Send
                  </button>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      </section>
      <section>
        <div className="admin-operations__summary">
          <div>
            <p className="workspace-kicker">Blog</p>
            <h2>Published, semantic, and indexed</h2>
            <p>Drafts stay private until an explicit Super Admin publication transition.</p>
          </div>
          <StatusBadge tone="info">/blog/slug</StatusBadge>
        </div>
        <form className="content-operations__form" onSubmit={createPost}>
          <label>
            Title
            <input name="title" required maxLength={180} />
          </label>
          <label>
            URL slug
            <input name="slug" required pattern="[a-z0-9]+(-[a-z0-9]+)*" maxLength={120} />
          </label>
          <label className="content-operations__wide">
            Excerpt
            <input name="excerpt" required maxLength={500} />
          </label>
          <label className="content-operations__wide">
            Article body
            <textarea name="content" required maxLength={50000} />
          </label>
          <button type="submit">Create Blog draft</button>
        </form>
        <div className="content-operations__rows">
          {posts.map((post) => (
            <article key={post.id}>
              <div>
                <strong>{post.title}</strong>
                <span>
                  /blog/{post.slug} · {post.excerpt}
                </span>
              </div>
              <StatusBadge tone="neutral">{post.state}</StatusBadge>
              <div className="content-operations__actions">
                {post.state === 'DRAFT' ? (
                  <button
                    type="button"
                    onClick={() =>
                      void command(`/api/v1/admin/blog/posts/${post.id}/ready`, {
                        reason: 'Content and SEO reviewed.',
                      })
                    }
                  >
                    Prepare
                  </button>
                ) : null}
                {['READY', 'SCHEDULED'].includes(post.state) ? (
                  <button
                    type="button"
                    onClick={() =>
                      void command(`/api/v1/admin/blog/posts/${post.id}/publish`, {
                        reason: 'Authorized publication.',
                      })
                    }
                  >
                    Publish
                  </button>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
