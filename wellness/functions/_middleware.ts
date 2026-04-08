// Intercept /robots.txt to serve our own version without Cloudflare's AI bot blocks
export const onRequest: PagesFunction = async (context) => {
  const url = new URL(context.request.url);

  if (url.pathname === '/robots.txt') {
    const robotsTxt = `User-agent: *
Allow: /

User-agent: GPTBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: CCBot
Allow: /

User-agent: Amazonbot
Allow: /

User-agent: Applebot-Extended
Allow: /

User-agent: Bytespider
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: meta-externalagent
Allow: /

User-agent: Diffbot
Allow: /

User-agent: cohere-ai
Allow: /

Sitemap: https://rooted-glow.com/sitemap-index.xml
`;
    return new Response(robotsTxt, {
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    });
  }

  return context.next();
};
