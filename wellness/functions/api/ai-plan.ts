interface Env {
  OPENAI_API_KEY: string;
}

const SYSTEM_PROMPT = `You are a warm, knowledgeable holistic wellness coach writing for Rooted Glow, a wellness blog focused on movement, sleep, stress management, and ancestral nutrition. You speak in a friendly, grounded tone — no hype, no jargon, just practical wisdom.

When given a user's wellness archetype and pillar scores, generate a personalised 7-day wellness plan. The plan should:
- Be specific and actionable (exact times, durations, foods)
- Address the user's weakest pillars most heavily
- Build on their existing strengths
- Feel achievable, not overwhelming
- Include one small "level up" challenge on Day 7

Format the plan in clean markdown with Day headers (## Day 1: [Theme]) and bullet points for each action. Keep each day to 3-4 actions max. End with a brief encouraging closing paragraph.`;

export const onRequestPost: PagesFunction<Env> = async (context) => {
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };

  if (context.request.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  const apiKey = context.env.OPENAI_API_KEY;
  if (!apiKey) {
    return new Response(JSON.stringify({ error: 'API key not configured' }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  let body: any;
  try {
    body = await context.request.json();
  } catch {
    return new Response(JSON.stringify({ error: 'Invalid JSON' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  const { scores, archetype, answers } = body;
  if (!scores || !archetype) {
    return new Response(JSON.stringify({ error: 'Missing scores or archetype' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  const userPrompt = `Here is the user's wellness profile:

**Archetype:** ${archetype.name} (${archetype.tagline})

**Pillar Scores (out of 100):**
- Movement: ${scores.movement}
- Sleep: ${scores.sleep}
- Stress: ${scores.stress}
- Nutrition: ${scores.nutrition}

**Strengths:** ${archetype.strengths.join(', ')}
**Growth Areas:** ${archetype.growthAreas.join(', ')}

Please create a personalised 7-day wellness plan for this person. Focus most on their weakest areas while reinforcing their strengths.`;

  try {
    const openaiRes = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        messages: [
          { role: 'system', content: SYSTEM_PROMPT },
          { role: 'user', content: userPrompt },
        ],
        stream: true,
        max_tokens: 1500,
        temperature: 0.7,
      }),
    });

    if (!openaiRes.ok) {
      const err = await openaiRes.text();
      return new Response(JSON.stringify({ error: 'OpenAI API error', details: err }), {
        status: 502,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    // Stream the SSE response through to the client
    const { readable, writable } = new TransformStream();
    const writer = writable.getWriter();
    const encoder = new TextEncoder();

    (async () => {
      const reader = openaiRes.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || !trimmed.startsWith('data: ')) continue;
            const data = trimmed.slice(6);
            if (data === '[DONE]') {
              await writer.write(encoder.encode('data: [DONE]\n\n'));
              continue;
            }
            try {
              const parsed = JSON.parse(data);
              const content = parsed.choices?.[0]?.delta?.content;
              if (content) {
                await writer.write(encoder.encode(`data: ${JSON.stringify({ content })}\n\n`));
              }
            } catch {}
          }
        }
      } catch (e) {
        await writer.write(encoder.encode(`data: ${JSON.stringify({ error: 'Stream interrupted' })}\n\n`));
      } finally {
        await writer.close();
      }
    })();

    return new Response(readable, {
      headers: {
        ...corsHeaders,
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
    });
  } catch (e: any) {
    return new Response(JSON.stringify({ error: 'Failed to reach OpenAI', message: e.message }), {
      status: 502,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
};
