interface Env {
  SUBSCRIBERS: KVNamespace;
  NEWSLETTER_SECRET: string;
}

async function hmac(secret: string, message: string): Promise<string> {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    enc.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(message));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

const PAGE = (title: string, message: string) => `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title} — Rooted Glow</title>
<style>body{font-family:system-ui,sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;background:#f0fdf4}
.card{text-align:center;max-width:420px;padding:3rem 2rem;background:#fff;border-radius:1.5rem;box-shadow:0 4px 24px rgba(0,0,0,.06)}
h1{color:#15803d;font-size:1.5rem;margin-bottom:.5rem}p{color:#64748b;line-height:1.6}
a{color:#16a34a;text-decoration:none;font-weight:600}</style></head>
<body><div class="card"><h1>${title}</h1><p>${message}</p><p><a href="https://rooted-glow.com">Back to Rooted Glow</a></p></div></body></html>`;

export const onRequestGet: PagesFunction<Env> = async (context) => {
  const url = new URL(context.request.url);
  const email = (url.searchParams.get('email') || '').trim().toLowerCase();
  const token = url.searchParams.get('token') || '';

  if (!email || !token) {
    return new Response(PAGE('Invalid Link', 'This unsubscribe link is missing required parameters.'), {
      status: 400,
      headers: { 'Content-Type': 'text/html; charset=utf-8' },
    });
  }

  const expected = await hmac(context.env.NEWSLETTER_SECRET, email);
  if (token !== expected) {
    return new Response(PAGE('Invalid Link', 'This unsubscribe link is not valid. Please check your email for the correct link.'), {
      status: 403,
      headers: { 'Content-Type': 'text/html; charset=utf-8' },
    });
  }

  await context.env.SUBSCRIBERS.delete(email);

  return new Response(PAGE('Unsubscribed', `<strong>${email}</strong> has been removed from our mailing list. You won&apos;t receive any more emails from us.`), {
    headers: { 'Content-Type': 'text/html; charset=utf-8' },
  });
};
