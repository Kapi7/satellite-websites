/**
 * Newsletter Admin API — Cloudflare Pages Function
 *
 * Handles authentication and subscriber management.
 * All actions go through POST to avoid caching.
 *
 * Actions:
 *   login    — { action: "login", email, password } → { token }
 *   list     — { action: "list" } + Authorization header → { subscribers }
 *   delete   — { action: "delete", email } + Authorization header
 *   add      — { action: "add", email, locale } + Authorization header
 *   export   — { action: "export" } + Authorization header → CSV
 */

interface Env {
  SUBSCRIBERS: KVNamespace;
  NEWSLETTER_SECRET: string;
  ADMIN_EMAIL: string;
  ADMIN_PASSWORD_HASH: string;
}

const enc = new TextEncoder();

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
};

function json(data: object, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  });
}

async function sha256(input: string): Promise<string> {
  const hash = await crypto.subtle.digest('SHA-256', enc.encode(input));
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

async function makeToken(secret: string, email: string): Promise<string> {
  const ts = Math.floor(Date.now() / 1000);
  const key = await crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(`${email}:${ts}`));
  const hmac = [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, '0')).join('');
  return `${ts}:${hmac}`;
}

async function verifyToken(secret: string, adminEmail: string, token: string): Promise<boolean> {
  const parts = token.split(':');
  if (parts.length !== 2) return false;
  const ts = parseInt(parts[0], 10);
  if (isNaN(ts)) return false;

  const now = Math.floor(Date.now() / 1000);
  if (now - ts > 86400) return false;

  const key = await crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(`${adminEmail}:${ts}`));
  const expected = [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, '0')).join('');
  return expected === parts[1];
}

async function requireAuth(request: Request, env: Env): Promise<boolean> {
  const auth = request.headers.get('Authorization') || '';
  const token = auth.replace('Bearer ', '');
  return verifyToken(env.NEWSLETTER_SECRET, env.ADMIN_EMAIL, token);
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export const onRequestPost: PagesFunction<Env> = async (context) => {
  const { request, env } = context;

  let body: any;
  try {
    body = await request.json();
  } catch {
    return json({ error: 'Invalid JSON' }, 400);
  }

  const action = body.action;

  if (action === 'login') {
    const email = (body.email || '').trim().toLowerCase();
    const password = body.password || '';

    if (email !== env.ADMIN_EMAIL.toLowerCase()) {
      return json({ error: 'Invalid credentials' }, 401);
    }

    const hash = await sha256(password);
    if (hash !== env.ADMIN_PASSWORD_HASH) {
      return json({ error: 'Invalid credentials' }, 401);
    }

    const token = await makeToken(env.NEWSLETTER_SECRET, email);
    return json({ token });
  }

  if (!(await requireAuth(request, env))) {
    return json({ error: 'Unauthorized' }, 401);
  }

  if (action === 'list') {
    const subscribers: any[] = [];
    let cursor: string | undefined;

    while (true) {
      const opts: KVNamespaceListOptions = { limit: 1000 };
      if (cursor) opts.cursor = cursor;
      const result = await env.SUBSCRIBERS.list(opts);

      for (const key of result.keys) {
        const val = await env.SUBSCRIBERS.get(key.name);
        let meta: any = {};
        if (val) {
          try { meta = JSON.parse(val); } catch {}
        }
        subscribers.push({
          email: key.name,
          locale: meta.locale || 'en',
          date: meta.date || '',
          confirmed: meta.confirmed ?? true,
        });
      }

      if (result.list_complete) break;
      cursor = result.cursor;
    }

    return json({ subscribers, count: subscribers.length });
  }

  if (action === 'delete') {
    const email = (body.email || '').trim().toLowerCase();
    if (!email) return json({ error: 'Email required' }, 400);

    await env.SUBSCRIBERS.delete(email);
    return json({ status: 'deleted', email });
  }

  if (action === 'add') {
    const email = (body.email || '').trim().toLowerCase();
    if (!email || !EMAIL_RE.test(email)) {
      return json({ error: 'Invalid email' }, 400);
    }

    const existing = await env.SUBSCRIBERS.get(email);
    if (existing) {
      return json({ status: 'already_exists', email });
    }

    await env.SUBSCRIBERS.put(email, JSON.stringify({
      locale: body.locale || 'en',
      date: new Date().toISOString(),
      confirmed: true,
    }));
    return json({ status: 'added', email });
  }

  if (action === 'export') {
    const rows: string[] = ['email,locale,date'];
    let cursor: string | undefined;

    while (true) {
      const opts: KVNamespaceListOptions = { limit: 1000 };
      if (cursor) opts.cursor = cursor;
      const result = await env.SUBSCRIBERS.list(opts);

      for (const key of result.keys) {
        const val = await env.SUBSCRIBERS.get(key.name);
        let meta: any = {};
        if (val) {
          try { meta = JSON.parse(val); } catch {}
        }
        rows.push(`${key.name},${meta.locale || 'en'},${meta.date || ''}`);
      }

      if (result.list_complete) break;
      cursor = result.cursor;
    }

    return new Response(rows.join('\n'), {
      headers: {
        ...corsHeaders,
        'Content-Type': 'text/csv',
        'Content-Disposition': 'attachment; filename="subscribers.csv"',
      },
    });
  }

  return json({ error: 'Unknown action' }, 400);
};

export const onRequestOptions: PagesFunction = async () => {
  return new Response(null, { headers: corsHeaders });
};
