import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';
import type { APIContext } from 'astro';

export async function GET(context: APIContext) {
  const posts = await getCollection('blog', ({ data }) => !data.draft);
  const sorted = posts.sort((a, b) => b.data.date.getTime() - a.data.date.getTime());

  return rss({
    title: 'Glow Coded',
    description: 'Skincare education, honest reviews, K-Beauty deep-dives, and ingredient breakdowns.',
    site: context.site!.href,
    items: sorted.map((post) => ({
      title: post.data.title,
      description: post.data.description,
      pubDate: post.data.date,
      link: `/${post.id}/`,
      categories: [post.data.category, ...(post.data.tags || [])],
    })),
  });
}
