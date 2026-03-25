/**
 * SEO utilities: JSON-LD schema generators and meta helpers.
 */

export interface ArticleMeta {
  title: string;
  description: string;
  url: string;
  image?: string;
  datePublished: string;
  dateModified?: string;
  author: string;
  publisher: string;
  publisherLogo?: string;
  category?: string;
  tags?: string[];
}

export function generateArticleSchema(meta: ArticleMeta): string {
  return JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: meta.title,
    description: meta.description,
    url: meta.url,
    image: meta.image,
    datePublished: meta.datePublished,
    dateModified: meta.dateModified || meta.datePublished,
    author: {
      '@type': 'Organization',
      name: meta.author,
    },
    publisher: {
      '@type': 'Organization',
      name: meta.publisher,
      logo: meta.publisherLogo
        ? { '@type': 'ImageObject', url: meta.publisherLogo }
        : undefined,
    },
    mainEntityOfPage: {
      '@type': 'WebPage',
      '@id': meta.url,
    },
  });
}

export interface BreadcrumbItem {
  name: string;
  url: string;
}

export function generateBreadcrumbSchema(items: BreadcrumbItem[]): string {
  return JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: item.url,
    })),
  });
}

export function generateOrganizationSchema(
  name: string,
  url: string,
  logo?: string,
  description?: string
): string {
  return JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name,
    url,
    logo: logo ? { '@type': 'ImageObject', url: logo } : undefined,
    description,
  });
}

export interface FaqItem {
  question: string;
  answer: string;
}

export function generateFaqSchema(items: FaqItem[]): string {
  return JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: items.map((item) => ({
      '@type': 'Question',
      name: item.question,
      acceptedAnswer: {
        '@type': 'Answer',
        text: item.answer,
      },
    })),
  });
}
