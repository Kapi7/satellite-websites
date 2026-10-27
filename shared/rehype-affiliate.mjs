// Qualify retailer links in the server-rendered article HTML.
const MIRAI_HOSTS = new Set(['mirai-skin.com', 'www.mirai-skin.com']);
const AMAZON_HOSTS = new Set(['amazon.com', 'www.amazon.com', 'amzn.to']);
const REL_EXTRA = ['sponsored', 'noopener', 'noreferrer'];

/**
 * @param {{ siteDomain?: string, campaign?: string }} [options]
 */
export default function rehypeAffiliate(options = {}) {
  const siteDomain = options.siteDomain || 'glow-coded.com';
  const campaign = options.campaign || 'mirai_skin';

  return (tree, file) => {
    const slugHint = slugFromFile(file);

    const walk = (node) => {
      if (node.type === 'element' && node.tagName === 'a') {
        const props = node.properties || {};
        try {
          const url = new URL(String(props.href));
          const host = url.hostname;

          if (MIRAI_HOSTS.has(host) || AMAZON_HOSTS.has(host)) {
            const rel = Array.isArray(props.rel)
              ? props.rel
              : String(props.rel || '').split(/\s+/);
            props.rel = [...new Set([...rel.filter(Boolean), ...REL_EXTRA])];
          }

          // UTM only for Mirai shop paths. Amazon stays rel-only.
          // Existing campaign params win so we never double-append.
          if (MIRAI_HOSTS.has(host) && isShopPath(url.pathname || '')) {
            let changed = false;
            if (!url.searchParams.has('utm_source')) {
              url.searchParams.set('utm_source', siteDomain);
              changed = true;
            }
            if (!url.searchParams.has('utm_medium')) {
              url.searchParams.set('utm_medium', 'affiliate');
              changed = true;
            }
            if (!url.searchParams.has('utm_campaign')) {
              url.searchParams.set('utm_campaign', campaign);
              changed = true;
            }
            if (slugHint && !url.searchParams.has('utm_content')) {
              url.searchParams.set('utm_content', `/${slugHint}/`);
              changed = true;
            }
            if (changed) props.href = url.href;
          }

          node.properties = props;
        } catch {
          /* relative / malformed — leave alone */
        }
      }
      for (const child of node.children || []) walk(child);
    };
    walk(tree);
  };
}

function isShopPath(pathname) {
  return (
    pathname === '/products' || pathname.startsWith('/products/') ||
    pathname === '/collections' || pathname.startsWith('/collections/') ||
    pathname === '/cart' || pathname.startsWith('/cart/') ||
    pathname.startsWith('/yt-')
  );
}

function slugFromFile(file) {
  const hist = (file && (file.path || (file.history && file.history[0]))) || '';
  const match = String(hist).match(/content\/blog\/(?:[a-z]{2}\/)?([^/]+)\.mdx$/i);
  return match ? match[1] : '';
}
