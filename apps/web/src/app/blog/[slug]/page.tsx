import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { BlogArticle } from '@/components/public-blog';

type ArticleMetadata = {
  title: string;
  excerpt: string;
  seo_title: string | null;
  meta_description: string | null;
  canonical_path: string;
  og_title: string | null;
  og_description: string | null;
  featured_image_url: string | null;
};

export const dynamic = 'force-dynamic';

async function articleMetadata(
  slug: string,
): Promise<{ post: ArticleMetadata | null; missing: boolean }> {
  const api = process.env.API_INTERNAL_URL ?? 'http://127.0.0.1:8000';
  try {
    const response = await fetch(`${api}/api/v1/blog/posts/${encodeURIComponent(slug)}`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(2_500),
    });
    if (response.status === 404) return { post: null, missing: true };
    if (!response.ok) return { post: null, missing: false };
    return { post: (await response.json()) as ArticleMetadata, missing: false };
  } catch {
    return { post: null, missing: false };
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { post } = await articleMetadata((await params).slug);
  if (!post) return { title: 'Article unavailable' };
  const title = post.seo_title ?? post.title;
  const description = post.meta_description ?? post.excerpt;
  return {
    title,
    description,
    alternates: { canonical: post.canonical_path },
    openGraph: {
      type: 'article',
      title: post.og_title ?? title,
      description: post.og_description ?? description,
      ...(post.featured_image_url ? { images: [post.featured_image_url] } : {}),
    },
  };
}

export default async function ArticlePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const result = await articleMetadata(slug);
  if (result.missing) notFound();
  return <BlogArticle slug={slug} />;
}
