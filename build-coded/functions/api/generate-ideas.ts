interface Env {
  OPENAI_API_KEY: string;
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

const VALID_SPACES = ['garage', 'backyard', 'bedroom', 'kitchen', 'bathroom', 'living-room', 'workshop', 'balcony'];
const VALID_SKILLS = ['beginner', 'intermediate', 'advanced'];
const VALID_BUDGETS = ['under-25', '25-50', '50-100', '100-250', '250-plus'];
const VALID_INTERESTS = ['woodworking', 'home-improvement', 'electronics', 'crafts', 'furniture', 'decor', 'organization', 'outdoor'];

const MAX_PHOTO_BYTES = 4 * 1024 * 1024; // 4MB

export const onRequestPost: PagesFunction<Env> = async (context) => {
  let body: any;
  try {
    body = await context.request.json();
  } catch {
    return json({ error: 'Invalid JSON' }, 400);
  }

  const { space, skillLevel, budget, interests, photoBase64 } = body;

  if (!space || !VALID_SPACES.includes(space)) {
    return json({ error: 'Invalid space selection' }, 400);
  }
  if (!skillLevel || !VALID_SKILLS.includes(skillLevel)) {
    return json({ error: 'Invalid skill level' }, 400);
  }
  if (!budget || !VALID_BUDGETS.includes(budget)) {
    return json({ error: 'Invalid budget selection' }, 400);
  }
  if (!Array.isArray(interests) || interests.length < 1 || interests.length > 4 || !interests.every((i: string) => VALID_INTERESTS.includes(i))) {
    return json({ error: 'Select 1-4 valid interests' }, 400);
  }

  if (photoBase64 && photoBase64.length > MAX_PHOTO_BYTES * 1.37) {
    return json({ error: 'Photo exceeds 4MB limit' }, 400);
  }

  const budgetLabel: Record<string, string> = {
    'under-25': 'Under $25',
    '25-50': '$25-50',
    '50-100': '$50-100',
    '100-250': '$100-250',
    '250-plus': '$250+',
  };

  const userPrompt = `Generate DIY project ideas for:
- Space: ${space.replace('-', ' ')}
- Skill level: ${skillLevel}
- Budget: ${budgetLabel[budget]}
- Interests: ${interests.join(', ')}
${photoBase64 ? '\nA photo of the space is attached — analyze it and tailor ideas to what you see.' : ''}

Return 3-5 creative, practical DIY project ideas as a JSON array.`;

  const systemPrompt = `You are an expert DIY project advisor. Return ONLY valid JSON — no markdown, no code fences, no explanation.

Return this exact structure:
{"ideas":[{"title":"...","description":"...","difficulty":"beginner|intermediate|advanced","estimatedCost":"$XX-XX","estimatedTime":"X hours|days","materialsNeeded":["item1","item2"],"firstStep":"..."}]}

Rules:
- 3-5 ideas that match the user's space, skill level, budget, and interests
- Descriptions should be 2-3 sentences, practical and inspiring
- firstStep should be a concrete, actionable first step to begin the project
- estimatedCost must fit within the stated budget
- difficulty must match the stated skill level (can be equal or easier, never harder)`;

  const messages: any[] = [{ role: 'system', content: systemPrompt }];

  if (photoBase64) {
    messages.push({
      role: 'user',
      content: [
        { type: 'text', text: userPrompt },
        { type: 'image_url', image_url: { url: `data:image/jpeg;base64,${photoBase64}`, detail: 'low' } },
      ],
    });
  } else {
    messages.push({ role: 'user', content: userPrompt });
  }

  try {
    const resp = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${context.env.OPENAI_API_KEY}`,
      },
      body: JSON.stringify({
        model: 'gpt-4o',
        messages,
        temperature: 0.8,
        max_tokens: 2000,
      }),
    });

    if (!resp.ok) {
      const err = await resp.text();
      console.error('OpenAI error:', resp.status, err);
      return json({ error: 'Failed to generate ideas. Please try again.' }, 502);
    }

    const data = await resp.json() as any;
    const content = data.choices?.[0]?.message?.content;
    if (!content) {
      return json({ error: 'Empty response from AI' }, 502);
    }

    const parsed = JSON.parse(content);
    return json(parsed);
  } catch (e: any) {
    console.error('generate-ideas error:', e.message);
    return json({ error: 'Something went wrong. Please try again.' }, 500);
  }
};

export const onRequestOptions: PagesFunction = async () => {
  return new Response(null, { headers: corsHeaders });
};
