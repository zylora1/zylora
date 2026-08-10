'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

import { apiRequest } from '@/lib/api';
import { PublicFooter, PublicNavigation, PublicSite } from './public-site';

type Post = {
  title: string;
  slug: string;
  excerpt: string;
  published_at: string | null;
  categories: string[];
  tags: string[];
};
type Article = Post & {
  content_html: string;
  featured_image_url: string | null;
  seo_title: string | null;
  meta_description: string | null;
  canonical_path: string;
  og_title: string | null;
  og_description: string | null;
};

function date(value: string | null) {
  return value
    ? new Intl.DateTimeFormat(undefined, { dateStyle: 'long' }).format(new Date(value))
    : '';
}

function articleSchema(post: Article) {
  return JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: post.seo_title ?? post.title,
    description: post.meta_description ?? post.excerpt,
    datePublished: post.published_at,
    mainEntityOfPage: post.canonical_path,
    author: { '@type': 'Organization', name: 'Zylora' },
    publisher: { '@type': 'Organization', name: 'Zylora' },
    ...(post.featured_image_url ? { image: [post.featured_image_url] } : {}),
  }).replace(/</g, '\\u003c');
}

export function BlogIndex() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    void apiRequest<Post[]>('/api/v1/blog/posts')
      .then(setPosts)
      .catch((reason: unknown) =>
        setError(reason instanceof Error ? reason.message : 'Blog is unavailable.'),
      );
  }, []);
  return (
    <PublicSite>
      <PublicNavigation />
      <main className="blog-shell">
        <header className="blog-hero">
          <p className="eyebrow">Zylora Journal</p>
          <h1>Clear thinking for considered websites.</h1>
          <p>Practical notes on shaping, publishing, and improving a Website you own.</p>
        </header>
        {error ? <p className="blog-message">{error}</p> : null}
        {!error && !posts.length ? (
          <p className="blog-message">No articles have been published yet.</p>
        ) : null}
        <section className="blog-list" aria-label="Published Blog posts">
          {posts.map((post) => (
            <article key={post.slug} className="blog-card">
              <p>{post.categories.join(' / ') || 'Zylora Journal'}</p>
              <h2>
                <Link href={`/blog/${post.slug}`}>{post.title}</Link>
              </h2>
              <p className="blog-card__excerpt">{post.excerpt}</p>
              <footer>
                <time dateTime={post.published_at ?? undefined}>{date(post.published_at)}</time>
                <Link href={`/blog/${post.slug}`}>Read article &rarr;</Link>
              </footer>
            </article>
          ))}
        </section>
      </main>
      <PublicFooter />
    </PublicSite>
  );
}

export function BlogArticle({ slug }: { slug: string }) {
  const [post, setPost] = useState<Article | null>(null);
  const [related, setRelated] = useState<Post[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    void Promise.all([
      apiRequest<Article>(`/api/v1/blog/posts/${encodeURIComponent(slug)}`),
      apiRequest<Post[]>('/api/v1/blog/posts'),
    ])
      .then(([article, posts]) => {
        setPost(article);
        setRelated(
          posts
            .filter(
              (candidate) =>
                candidate.slug !== article.slug &&
                candidate.categories.some((category) => article.categories.includes(category)),
            )
            .slice(0, 3),
        );
      })
      .catch((reason: unknown) =>
        setError(reason instanceof Error ? reason.message : 'Article is unavailable.'),
      );
  }, [slug]);
  return (
    <PublicSite>
      <PublicNavigation />
      <main className="blog-shell">
        {error ? <p className="blog-message">{error}</p> : null}
        {!error && !post ? <p className="blog-message">Loading article...</p> : null}
        {post ? (
          <article className="blog-article">
            <script
              type="application/ld+json"
              dangerouslySetInnerHTML={{ __html: articleSchema(post) }}
            />
            <nav className="blog-breadcrumb" aria-label="Breadcrumb">
              <Link href="/">Home</Link>
              <span aria-hidden="true">/</span>
              <Link href="/blog">Journal</Link>
              <span aria-hidden="true">/</span>
              <span aria-current="page">{post.title}</span>
            </nav>
            <p className="eyebrow">{post.categories.join(' / ') || 'Zylora Journal'}</p>
            <h1>{post.title}</h1>
            <p className="blog-article__excerpt">{post.excerpt}</p>
            <p className="blog-article__meta">
              <time dateTime={post.published_at ?? undefined}>{date(post.published_at)}</time>
              {post.tags.length ? ` / ${post.tags.join(', ')}` : ''}
            </p>
            {post.featured_image_url ? (
              // This is a Super Admin-provided external Open Graph asset, not a customer upload.
              // eslint-disable-next-line @next/next/no-img-element
              <img src={post.featured_image_url} alt="" />
            ) : null}
            <div
              className="blog-article__body"
              dangerouslySetInnerHTML={{ __html: post.content_html }}
            />
            {related.length ? (
              <aside className="blog-related" aria-label="Related articles">
                <h2>Continue reading</h2>
                <ul>
                  {related.map((item) => (
                    <li key={item.slug}>
                      <Link href={`/blog/${item.slug}`}>{item.title}</Link>
                    </li>
                  ))}
                </ul>
              </aside>
            ) : null}
            <footer>
              <Link href="/blog">&larr; All articles</Link>
            </footer>
          </article>
        ) : null}
      </main>
      <PublicFooter />
    </PublicSite>
  );
}
