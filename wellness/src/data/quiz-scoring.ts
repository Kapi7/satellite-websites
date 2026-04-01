import { pillarMaxScores } from './quiz-questions';
import { archetypes } from './quiz-archetypes';
import type { Archetype } from './quiz-archetypes';

export interface PillarScores {
  movement: number;
  sleep: number;
  stress: number;
  nutrition: number;
}

export interface QuizResult {
  scores: PillarScores;
  normalised: PillarScores;
  archetype: Archetype;
}

/**
 * Sum raw scores per pillar from quiz answers.
 * answers: Record<questionId, selectedScore>
 */
export function calculateScores(
  answers: Record<number, number>,
  questions: { id: number; pillar: string }[]
): PillarScores {
  const scores: PillarScores = { movement: 0, sleep: 0, stress: 0, nutrition: 0 };
  for (const q of questions) {
    const answer = answers[q.id];
    if (answer !== undefined) {
      scores[q.pillar as keyof PillarScores] += answer;
    }
  }
  return scores;
}

/**
 * Normalise raw scores to 0-100 scale.
 */
export function normaliseScores(raw: PillarScores): PillarScores {
  return {
    movement: Math.round((raw.movement / pillarMaxScores.movement) * 100),
    sleep: Math.round((raw.sleep / pillarMaxScores.sleep) * 100),
    stress: Math.round((raw.stress / pillarMaxScores.stress) * 100),
    nutrition: Math.round((raw.nutrition / pillarMaxScores.nutrition) * 100),
  };
}

/**
 * Determine archetype from normalised scores using priority rules.
 */
export function determineArchetype(n: PillarScores): Archetype {
  const avg = (n.movement + n.sleep + n.stress + n.nutrition) / 4;

  // 1. All pillars >= 60 -> balanced-root
  if (n.movement >= 60 && n.sleep >= 60 && n.stress >= 60 && n.nutrition >= 60) {
    return find('balanced-root');
  }

  // 2. Average < 40 -> fresh-starter
  if (avg < 40) {
    return find('fresh-starter');
  }

  // 3. Sleep < 40 + others >= 50 -> sleep-seeker
  if (n.sleep < 40 && n.movement >= 50 && n.stress >= 50 && n.nutrition >= 50) {
    return find('sleep-seeker');
  }

  // 4. Stress < 40 + others >= 50 -> stress-survivor
  if (n.stress < 40 && n.movement >= 50 && n.sleep >= 50 && n.nutrition >= 50) {
    return find('stress-survivor');
  }

  // 5. (Nutrition>=60 or Movement>=60) + (Sleep<45 or Stress<45) -> restless-achiever
  if ((n.nutrition >= 60 || n.movement >= 60) && (n.sleep < 45 || n.stress < 45)) {
    return find('restless-achiever');
  }

  // 6. Movement>=60 + Nutrition>=60 -> grounded-mover
  if (n.movement >= 60 && n.nutrition >= 60) {
    return find('grounded-mover');
  }

  // 7. Sleep>=60 + Nutrition>=60 -> restful-nurturer
  if (n.sleep >= 60 && n.nutrition >= 60) {
    return find('restful-nurturer');
  }

  // 8. Stress>=60 + Movement>=60 -> calm-explorer
  if (n.stress >= 60 && n.movement >= 60) {
    return find('calm-explorer');
  }

  // 9. Fallback: closest match by score profile
  return findClosest(n);
}

function find(slug: string): Archetype {
  return archetypes.find((a) => a.slug === slug)!;
}

/**
 * Fallback: score each archetype by how well the user's profile matches
 * the archetype's expected pattern, then pick the best fit.
 */
function findClosest(n: PillarScores): Archetype {
  const profiles: Record<string, PillarScores> = {
    'balanced-root':     { movement: 70, sleep: 70, stress: 70, nutrition: 70 },
    'grounded-mover':    { movement: 80, sleep: 40, stress: 40, nutrition: 80 },
    'restful-nurturer':  { movement: 35, sleep: 80, stress: 50, nutrition: 80 },
    'calm-explorer':     { movement: 75, sleep: 45, stress: 80, nutrition: 45 },
    'restless-achiever': { movement: 70, sleep: 30, stress: 30, nutrition: 65 },
    'sleep-seeker':      { movement: 55, sleep: 20, stress: 55, nutrition: 55 },
    'stress-survivor':   { movement: 55, sleep: 55, stress: 20, nutrition: 55 },
    'fresh-starter':     { movement: 25, sleep: 25, stress: 25, nutrition: 25 },
  };

  let bestSlug = 'fresh-starter';
  let bestDist = Infinity;

  for (const [slug, profile] of Object.entries(profiles)) {
    const dist = Math.sqrt(
      (n.movement - profile.movement) ** 2 +
      (n.sleep - profile.sleep) ** 2 +
      (n.stress - profile.stress) ** 2 +
      (n.nutrition - profile.nutrition) ** 2
    );
    if (dist < bestDist) {
      bestDist = dist;
      bestSlug = slug;
    }
  }

  return find(bestSlug);
}
