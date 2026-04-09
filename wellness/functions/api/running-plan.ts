interface Env {
  OPENAI_API_KEY: string;
}

const VALID_DISTANCES = ['5k', '10k', 'half'];
const VALID_LEVELS = ['beginner', 'intermediate', 'advanced', 'expert'];

const SYSTEM_PROMPT = `You are a certified running coach writing for Rooted Glow, a wellness blog. You speak in a friendly, knowledgeable tone — encouraging but realistic.

When given a user's race distance, experience level, and optional details, generate a structured week-by-week training plan in markdown.

The plan should:
- Be appropriate for the distance and level
- Include weekly structure with ## Week N headers
- Specify daily workouts: easy runs, intervals, tempo runs, long runs, rest days, cross-training
- Include pace zone guidelines (easy, moderate, tempo, interval)
- Build volume gradually (no more than 10% weekly increase)
- Include a taper week before race day
- End with race-week instructions and brief tips

Use clean markdown with ## headers for weeks, **bold** for workout types, and bullet points for daily details. Keep it practical and motivating.`;

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

  const { distance, level, daysPerWeek, weeklyKm, goalTime } = body;

  if (!distance || !VALID_DISTANCES.includes(distance)) {
    return new Response(JSON.stringify({ error: 'Invalid distance. Must be 5k, 10k, or half' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  if (!level || !VALID_LEVELS.includes(level)) {
    return new Response(JSON.stringify({ error: 'Invalid level. Must be beginner, intermediate, advanced, or expert' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  const distanceLabels: Record<string, string> = { '5k': '5K', '10k': '10K', 'half': 'Half Marathon (21.1 km)' };

  let userPrompt = `Create a training plan for a **${level}** runner preparing for a **${distanceLabels[distance]}** race.`;

  if (daysPerWeek) userPrompt += `\n- Available training days: ${daysPerWeek} days per week`;
  if (weeklyKm) userPrompt += `\n- Current weekly volume: ${weeklyKm} km`;
  if (goalTime) userPrompt += `\n- Goal time: ${goalTime}`;

  userPrompt += `\n\nPlease generate a complete week-by-week training plan with pace guidelines, rest days, and a taper week.`;

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
        max_tokens: 2500,
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
