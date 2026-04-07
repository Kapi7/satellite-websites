interface Env {
  SUBSCRIBERS: KVNamespace;
  NEWSLETTER_SECRET: string;
}

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

function json(data: object, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  });
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export const onRequestPost: PagesFunction<Env> = async (context) => {
  let body: any;
  try {
    body = await context.request.json();
  } catch {
    return json({ error: 'Invalid JSON' }, 400);
  }

  const email = (body.email || '').trim().toLowerCase();
  if (!email || !EMAIL_RE.test(email)) {
    return json({ error: 'invalid_email' }, 400);
  }

  const existing = await context.env.SUBSCRIBERS.get(email);
  if (existing) {
    return json({ status: 'already_subscribed' });
  }

  await context.env.SUBSCRIBERS.put(
    email,
    JSON.stringify({
      locale: body.locale || 'en',
      date: new Date().toISOString(),
      confirmed: true,
    }),
  );

  return json({ status: 'subscribed' });
};

export const onRequestOptions: PagesFunction = async () => {
  return new Response(null, { headers: corsHeaders });
};
