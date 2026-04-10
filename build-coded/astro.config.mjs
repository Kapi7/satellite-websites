// @ts-check
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';
import remarkGfm from 'remark-gfm';
import fs from 'node:fs';
import path from 'node:path';

// Build slug-to-date map from blog frontmatter for sitemap lastmod
const blogDir = './src/content/blog';
const slugDateMap = new Map();
function scanDir(dir) {
  if (!fs.existsSync(dir)) return;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      scanDir(path.join(dir, entry.name));
    } else if (entry.name.endsWith('.mdx')) {
      const content = fs.readFileSync(path.join(dir, entry.name), 'utf-8');
      const slug = entry.name.replace(/\.mdx$/, '');
      const updatedMatch = content.match(/^updated:\s*['"]?(\d{4}-\d{2}-\d{2})['"]?/m);
      const dateMatch = content.match(/^date:\s*['"]?(\d{4}-\d{2}-\d{2})['"]?/m);
      const d = updatedMatch?.[1] || dateMatch?.[1];
      if (d) slugDateMap.set(slug, d);
    }
  }
}
scanDir(blogDir);

const locales = ['en', 'es', 'de', 'el', 'ru', 'it', 'ar', 'fr', 'nl', 'pt'];
const sitemapLocales = Object.fromEntries(locales.map(l => [l, l]));

export default defineConfig({
  site: 'https://build-coded.com',
  trailingSlash: 'always',
  i18n: {
    defaultLocale: 'en',
    locales: locales,
    routing: {
      prefixDefaultLocale: false,
    },
  },
  integrations: [
    mdx({ remarkPlugins: [remarkGfm] }),
    sitemap({
      i18n: {
        defaultLocale: 'en',
        locales: sitemapLocales,
      },
      serialize(item) {
        const slug = item.url.replace('https://build-coded.com/', '').replace(/\/$/, '');
        // Strip locale prefix to match slug
        const cleanSlug = slug.replace(/^(es|de|el|ru|it|ar|fr|nl|pt)\//, '');
        const d = slugDateMap.get(cleanSlug);
        if (d) item.lastmod = new Date(d).toISOString();
        return item;
      },
    }),
  ],
  vite: {
    plugins: [tailwindcss()],
  },
});
