import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';
import type { APIContext } from 'astro';
import { locales, defaultLocale, type Locale } from '../../i18n/locales';
import { localePath } from '../../i18n/utils';

export function getStaticPaths() {
  return locales.map(l => ({
    params: { locale: l === defaultLocale ? undefined : l },
    props: { locale: l },
  }));
}

export async function GET(context: APIContext) {
  const locale = (context.props.locale || defaultLocale) as Locale;
  const now = new Date();
  const posts = await getCollection('blog', ({ data }) => !data.draft && data.locale === locale && data.date <= now);
  const sorted = posts.sort((a, b) => b.data.date.getTime() - a.data.date.getTime());

  return rss({
    title: 'Rooted Glow',
    description: 'Wellness, ancestral nutrition, movement, and K-Beauty grounded in real experience.',
    site: context.site!.href,
    items: sorted.map((post) => {
      const slug = post.id.includes('/') ? post.id.split('/').slice(1).join('/') : post.id;
      return {
        title: post.data.title,
        description: post.data.description,
        pubDate: post.data.date,
        link: localePath(`/${slug}/`, locale),
        categories: [post.data.category, ...(post.data.tags || [])],
      };
    }),
  });
}
