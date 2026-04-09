interface Env {
  OPENAI_API_KEY: string;
}

const VALID_MEALS = ['breakfast', 'lunch', 'dinner', 'snack'];
const VALID_GOALS = ['high-protein', 'anti-inflammatory', 'gut-health', 'weight-loss', 'energy', 'recovery'];
const VALID_RESTRICTIONS = ['gluten-free', 'dairy-free', 'vegetarian', 'vegan', 'keto', 'paleo', 'nut-free'];

const SYSTEM_PROMPT = `You are a nutrition-focused chef aligned with Rooted Glow's ancestral, whole-food philosophy. You create recipes that are nourishing, practical, and made from real ingredients — no processed foods, seed oils, or artificial additives.

When given a meal type, dietary goals, restrictions, and optional ingredients, generate ONE complete recipe in markdown:

Format:
# [Creative Recipe Name]

**Prep Time:** X min | **Cook Time:** X min | **Servings:** X

## Nutritional Highlights
Brief 2-3 bullet points about key nutrients and how they support the chosen goals.

## Ingredients
- List each ingredient with amount

## Instructions
1. Numbered step-by-step instructions
2. Keep steps clear and concise

## Tips & Variations
- 2-3 practical tips or ingredient swaps

Keep the tone warm and encouraging. Focus on whole, seasonal ingredients. If the user provides specific ingredients, incorporate them naturally.`;

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

  const { mealType, goals, restrictions, ingredients } = body;

  if (!mealType || !VALID_MEALS.includes(mealType)) {
    return new Response(JSON.stringify({ error: 'Invalid meal type' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  if (!goals || !Array.isArray(goals) || goals.length === 0 || goals.length > 3) {
    return new Response(JSON.stringify({ error: 'Please select 1-3 dietary goals' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  const goalLabels: Record<string, string> = {
    'high-protein': 'High Protein',
    'anti-inflammatory': 'Anti-Inflammatory',
    'gut-health': 'Gut Health',
    'weight-loss': 'Weight Loss',
    'energy': 'Energy Boost',
    'recovery': 'Recovery',
  };

  let userPrompt = `Create a **${mealType}** recipe optimised for: **${goals.map((g: string) => goalLabels[g] || g).join(', ')}**.`;

  if (restrictions && restrictions.length > 0) {
    userPrompt += `\n\nDietary restrictions: ${restrictions.join(', ')}.`;
  }

  if (ingredients && ingredients.trim()) {
    userPrompt += `\n\nThe user has these ingredients available: ${ingredients.trim()}. Try to incorporate them.`;
  }

  userPrompt += `\n\nGenerate one complete recipe with full details.`;

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
        temperature: 0.8,
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
