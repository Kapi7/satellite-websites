// @ts-check
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';
import fs from 'node:fs';
import path from 'node:path';

// Build slug-to-date map from blog frontmatter for sitemap lastmod
const blogDir = './src/content/blog';
const slugDateMap = new Map();
if (fs.existsSync(blogDir)) {
  for (const file of fs.readdirSync(blogDir).filter(f => f.endsWith('.mdx'))) {
    const content = fs.readFileSync(path.join(blogDir, file), 'utf-8');
    const slug = file.replace(/\.mdx$/, '');
    const updatedMatch = content.match(/^updated:\s*['"]?(\d{4}-\d{2}-\d{2})['"]?/m);
    const dateMatch = content.match(/^date:\s*['"]?(\d{4}-\d{2}-\d{2})['"]?/m);
    const d = updatedMatch?.[1] || dateMatch?.[1];
    if (d) slugDateMap.set(slug, d);
  }
}

export default defineConfig({
  site: 'https://glow-coded.com',
  integrations: [
    mdx(),
    sitemap({
      serialize(item) {
        const slug = item.url.replace('https://glow-coded.com/', '').replace(/\/$/, '');
        const d = slugDateMap.get(slug);
        if (d) item.lastmod = new Date(d).toISOString();
        return item;
      },
    }),
  ],
  vite: {
    plugins: [tailwindcss()],
  },
});
