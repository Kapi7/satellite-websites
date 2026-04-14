import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const blog = defineCollection({
  loader: glob({ pattern: '**/*.mdx', base: './src/content/blog' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    date: z.coerce.date(),
    updated: z.coerce.date().optional(),
    category: z.enum([
      'woodworking',
      'home-improvement',
      'electronics',
      'crafts',
    ]),
    type: z.enum(['hub', 'guide', 'listicle', 'review']),
    tags: z.array(z.string()).default([]),
    image: z.string().optional(),
    imageAlt: z.string().optional(),
    draft: z.boolean().default(false),
    affiliateProduct: z.string().optional(),
    hub: z.string().optional(),
    difficulty: z.enum(['beginner', 'intermediate', 'advanced']).optional(),
    estimatedTime: z.string().optional(),
    estimatedCost: z.string().optional(),
    locale: z.enum(['en', 'es', 'de', 'el', 'ru', 'it', 'ar', 'fr', 'nl', 'pt']).default('en'),
    author: z.string().optional(),
  }),
});

const authors = defineCollection({
  loader: glob({ pattern: '**/*.json', base: './src/content/authors' }),
  schema: z.object({
    name: z.string(),
    bio: z.string(),
    avatar: z.string().optional(),
  }),
});

const pages = defineCollection({
  loader: glob({ pattern: '**/*.mdx', base: './src/content/pages' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    locale: z.enum(['en', 'es', 'de', 'el', 'ru', 'it', 'ar', 'fr', 'nl', 'pt']).default('en'),
  }),
});

export const collections = { blog, authors, pages };
