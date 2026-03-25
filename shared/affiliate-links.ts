/**
 * Central Mirai product URL map.
 * IMPORTANT: Affiliate links are NOT active at launch.
 * This file is prepared for Phase 2 when we add monetization.
 * UTM source will be the satellite site domain (not youtube).
 */

export interface MiraiProduct {
  slug: string;
  name: string;
  path: string;
  description: string;
}

export const MIRAI_PRODUCTS: Record<string, MiraiProduct> = {
  'collection-all': {
    slug: 'collection-all',
    name: 'Mirai Full Collection',
    path: '/collections/all',
    description: 'Browse the complete Mirai skincare range.',
  },
  'routine': {
    slug: 'routine',
    name: 'Mirai Routine Set',
    path: '/yt-routine',
    description: 'Everything you need for a complete K-Beauty routine.',
  },
  'glow': {
    slug: 'glow',
    name: 'Mirai Glow Serum',
    path: '/yt-glow',
    description: 'Brightening serum for radiant, glass-like skin.',
  },
  'snail': {
    slug: 'snail',
    name: 'Mirai Snail Mucin',
    path: '/yt-snail',
    description: 'Hydrating snail mucin essence for repair and moisture.',
  },
  'acne': {
    slug: 'acne',
    name: 'Mirai Acne Care',
    path: '/yt-acne',
    description: 'Targeted treatment for breakout-prone skin.',
  },
  'moisture': {
    slug: 'moisture',
    name: 'Mirai Deep Moisture',
    path: '/yt-moisture',
    description: 'Rich hydration for dry and dehydrated skin.',
  },
  'sun': {
    slug: 'sun',
    name: 'Mirai Sunscreen',
    path: '/yt-sun',
    description: 'Lightweight Korean sunscreen, no white cast.',
  },
  'hair': {
    slug: 'hair',
    name: 'Mirai Hair Oil',
    path: '/yt-hair',
    description: 'Nourishing hair oil inspired by Korean beauty.',
  },
  'eye': {
    slug: 'eye',
    name: 'Mirai Eye Cream',
    path: '/yt-eye',
    description: 'Brightening eye cream for dark circles.',
  },
  'lip': {
    slug: 'lip',
    name: 'Mirai Lip Mask',
    path: '/yt-lip',
    description: 'Overnight lip treatment for soft, hydrated lips.',
  },
  'masks': {
    slug: 'masks',
    name: 'Mirai Sheet Masks',
    path: '/yt-masks',
    description: 'Premium sheet masks for weekly skin treatments.',
  },
};

export const MIRAI_BASE_URL = 'https://mirai-skin.com';

/**
 * Build a full affiliate URL with UTM tracking.
 * @param productSlug - Key from MIRAI_PRODUCTS
 * @param siteDomain - The satellite site domain (e.g., 'rooted-glow.com')
 * @param articleSlug - The article slug for campaign tracking
 */
export function buildAffiliateUrl(
  productSlug: string,
  siteDomain: string,
  articleSlug: string
): string {
  const product = MIRAI_PRODUCTS[productSlug];
  if (!product) return MIRAI_BASE_URL;

  const params = new URLSearchParams({
    utm_source: siteDomain,
    utm_medium: 'affiliate',
    utm_campaign: articleSlug,
  });

  return `${MIRAI_BASE_URL}${product.path}?${params.toString()}`;
}
