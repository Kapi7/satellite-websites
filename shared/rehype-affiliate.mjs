// Qualify retailer links in the server-rendered article HTML.
export default function rehypeAffiliate() {
  return tree => {
    const walk = node => {
      if (node.type === 'element' && node.tagName === 'a') {
        const props = node.properties || {};
        try {
          const url = new URL(String(props.href));
          if (['mirai-skin.com', 'www.mirai-skin.com', 'amazon.com', 'www.amazon.com', 'amzn.to'].includes(url.hostname)) {
            const rel = Array.isArray(props.rel) ? props.rel : String(props.rel || '').split(/\s+/);
            props.rel = [...new Set([...rel.filter(Boolean), 'sponsored', 'noopener', 'noreferrer'])];
            node.properties = props;
          }
        } catch { /* Local links are unchanged. */ }
      }
      for (const child of node.children || []) walk(child);
    };
    walk(tree);
  };
}
