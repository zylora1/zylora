import type { Metadata } from 'next';

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

async function articleMetadata(slug: string): Promise<ArticleMetadata | null> {
  const api = process.env.API_INTERNAL_URL ?? 'http://127.0.0.1:8000';
  const response = await fetch(`${api}/api/v1/blog/posts/${encodeURIComponent(slug)}`, {
    cache: 'no-store',
  });
  if (!response.ok) return null;
  return (await response.json()) as ArticleMetadata;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const post = await articleMetadata((await params).slug);
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
  return <BlogArticle slug={(await params).slug} />;
}
