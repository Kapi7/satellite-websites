export interface Product {
  name: string;
  image: string;
  url: string;
}

export function extractProducts(rawContent: string): Product[] {
  const pattern = /\[!\[([^\]]*)\]\(([^)]+)\)\]\((https?:\/\/[^)]*amazon\.com[^)]+)\)/g;
  const seen = new Set<string>();
  const products: Product[] = [];

  let match;
  while ((match = pattern.exec(rawContent)) !== null) {
    const url = match[3];
    if (seen.has(url)) continue;
    seen.add(url);
    products.push({ name: match[1], image: match[2], url });
  }

  return products;
}
