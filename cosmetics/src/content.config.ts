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
      'skincare',
      'ingredients',
      'reviews',
      'how-tos',
    ]),
    type: z.enum(['hub', 'guide', 'listicle', 'review', 'routine']),
    tags: z.array(z.string()).default([]),
    image: z.string().optional(),
    imageAlt: z.string().optional(),
    draft: z.boolean().default(false),
    affiliateProduct: z.string().optional(),
    hub: z.string().optional(),
    routine: z.string().optional(),
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

const ingredients = defineCollection({
  loader: glob({ pattern: '**/*.json', base: './src/content/ingredients' }),
  schema: z.object({
    name: z.string(),
    slug: z.string(),
    category: z.string(),
    benefits: z.array(z.string()),
    skinTypes: z.array(z.string()),
    comedogenicRating: z.number().min(0).max(5),
    description: z.string(),
    relatedProducts: z.array(z.object({
      name: z.string(),
      url: z.string(),
    })).default([]),
    conflicts: z.array(z.string()).default([]),
    pairsWith: z.array(z.string()).default([]),
  }),
});

export const collections = { blog, authors, ingredients };
