export interface Archetype {
  slug: string;
  name: string;
  tagline: string;
  description: string;
  strengths: string[];
  growthAreas: string[];
  topArticles: string[];
  alsoRecommended: string[];
  quickStartPlan: string[];
  ogTitle: string;
  seoDescription: string;
}

export const archetypes: Archetype[] = [
  {
    slug: 'balanced-root',
    name: 'The Balanced Root',
    tagline: 'Strong foundations across all four pillars',
    description:
      "You've built a solid wellness foundation across movement, sleep, stress management, and nutrition. You move regularly, sleep well, handle stress with awareness, and nourish your body with real food. You've got the basics down. The next step is going deeper and staying consistent when life gets busy.",
    strengths: ['Consistent daily routines', 'Good body awareness', 'Balanced approach to health'],
    growthAreas: ['Avoiding complacency', 'Deepening existing practices', 'Sharing what works with others'],
    topArticles: ['my-complete-am-wellness-routine', 'sleep-stress-skin-wellness-triangle'],
    alsoRecommended: ['meditation-for-beginners-start-5-minutes', 'seasonal-fruit-guide-what-to-eat-each-month', 'morning-mobility-routine-15-min'],
    quickStartPlan: [
      'Day 1: Audit your current routine. Write down what you do for each pillar',
      'Day 2: Add 5 minutes of mobility work to your morning',
      'Day 3: Try a new whole-food recipe you haven\'t made before',
      'Day 4: Extend your evening wind-down by 15 minutes',
      'Day 5: Take your regular workout outdoors',
      'Day 6: Try a 10-minute breathwork session',
      'Day 7: Reflect on the week. What felt different?',
    ],
    ogTitle: "I'm The Balanced Root",
    seoDescription: 'The Balanced Root wellness archetype. Strong foundations across movement, sleep, stress, and nutrition. Get personalised tips to deepen your practice.',
  },
  {
    slug: 'grounded-mover',
    name: 'The Grounded Mover',
    tagline: 'Strong body, nourished with real food',
    description:
      "Your body is your priority and it shows. You move with intention, whether it's strength training, hiking, or daily walks, and you fuel that movement with whole, nutrient-dense food. Where you might have room to grow is in recovery: sleep quality and stress management could be the missing pieces that take your physical health to the next level.",
    strengths: ['Active lifestyle', 'Good food choices', 'Physical resilience'],
    growthAreas: ['Recovery and rest', 'Stress management', 'Balancing output with input'],
    topArticles: ['functional-fitness-for-real-life', 'complete-guide-ancestral-eating'],
    alsoRecommended: ['morning-mobility-routine-15-min', 'bone-broth-benefits', 'high-protein-breakfasts-without-grains', 'why-we-quit-seed-oils'],
    quickStartPlan: [
      'Day 1: Add a 15-minute morning mobility routine before your workout',
      'Day 2: Make a bone broth and sip it as your afternoon snack',
      'Day 3: Replace one intense workout with a long walk',
      'Day 4: Set a "screens off" alarm 1 hour before bed',
      'Day 5: Try 5 minutes of box breathing post-workout',
      'Day 6: Cook a high-protein breakfast with seasonal ingredients',
      'Day 7: Take a full rest day. Walk, stretch, nothing more',
    ],
    ogTitle: "I'm The Grounded Mover",
    seoDescription: 'The Grounded Mover wellness archetype. Strong movement and nutrition habits. Discover how to improve recovery and stress for peak performance.',
  },
  {
    slug: 'restful-nurturer',
    name: 'The Restful Nurturer',
    tagline: 'Deep rest and mindful nourishment',
    description:
      "You understand that wellness starts from the inside. You prioritise sleep, eat well, and give your body the fuel and rest it needs. Movement and stress management might be areas where you could build more consistency. Adding regular physical activity and a simple breathwork practice could amplify everything you're already doing well.",
    strengths: ['Quality sleep habits', 'Nourishing food choices', 'Self-care awareness'],
    growthAreas: ['Regular movement', 'Stress resilience', 'Building physical strength'],
    topArticles: ['how-to-fix-your-sleep-in-7-days', 'gut-skin-connection-explained'],
    alsoRecommended: ['walking-for-health-underrated-exercise', 'fermented-beetroot-kvass-probiotic-drink', 'how-to-make-sauerkraut-at-home'],
    quickStartPlan: [
      'Day 1: Take a 20-minute walk after your biggest meal',
      'Day 2: Try a simple fermented food recipe (sauerkraut or kvass)',
      'Day 3: Do a 15-minute bodyweight workout (squats, push-ups, planks)',
      'Day 4: Write down 3 things you\'re grateful for before bed',
      'Day 5: Walk for 30 minutes outdoors, no headphones',
      'Day 6: Try 5 minutes of morning stretching',
      'Day 7: Cook something new with seasonal produce',
    ],
    ogTitle: "I'm The Restful Nurturer",
    seoDescription: 'The Restful Nurturer wellness archetype. Great sleep and nutrition habits. Learn how to add movement and stress management to complete your wellness picture.',
  },
  {
    slug: 'calm-explorer',
    name: 'The Calm Explorer',
    tagline: 'Moving through life with presence',
    description:
      "You've found a rhythm between physical activity and inner calm that many people envy. Whether it's walking, running, yoga, or just being outdoors, you move your body and manage stress with real awareness. Nutrition and sleep could use some attention. Dialling in your food quality and sleep hygiene will give you even more energy for the things you love.",
    strengths: ['Stress resilience', 'Regular movement', 'Mind-body connection'],
    growthAreas: ['Nutrition quality', 'Sleep consistency', 'Fuelling your activity properly'],
    topArticles: ['walking-for-health-underrated-exercise', '8-adaptogens-that-actually-work'],
    alsoRecommended: ['meditation-for-beginners-start-5-minutes', 'zone-2-training-slow-running-burns-fat', 'meditation-cortisol-stillness-heals-skin'],
    quickStartPlan: [
      'Day 1: Track everything you eat today. No judgement, just awareness',
      'Day 2: Replace one processed meal with a whole-food alternative',
      'Day 3: Set a consistent bedtime and wake time for the week',
      'Day 4: Try cooking with ghee or olive oil instead of seed oils',
      'Day 5: Do a walking meditation. 20 minutes, focused on breath',
      'Day 6: Make a high-protein breakfast',
      'Day 7: Reflect. How did your energy change this week?',
    ],
    ogTitle: "I'm The Calm Explorer",
    seoDescription: 'The Calm Explorer wellness archetype. Great movement and stress management. Discover how improving nutrition and sleep can help you reach your full potential.',
  },
  {
    slug: 'restless-achiever',
    name: 'The Restless Achiever',
    tagline: 'High output, low recovery',
    description:
      "You push hard, whether it's at the gym, at work, or in life. Your movement and nutrition might be solid, but your body isn't getting the recovery it needs. Poor sleep or unmanaged stress is likely holding you back more than any workout plan ever could. The gains you're chasing live in rest, not in more effort.",
    strengths: ['Drive and discipline', 'Physical activity', 'Goal-oriented mindset'],
    growthAreas: ['Sleep quality', 'Stress management', 'Learning to rest without guilt'],
    topArticles: ['how-to-fix-your-sleep-in-7-days', '8-adaptogens-that-actually-work'],
    alsoRecommended: ['sleep-stress-skin-wellness-triangle', 'meditation-cortisol-stillness-heals-skin', 'toxin-free-living-where-to-start'],
    quickStartPlan: [
      'Day 1: No screens after 9 PM. Read a book instead',
      'Day 2: Replace your hardest workout with a 45-minute walk',
      'Day 3: Try 10 minutes of guided meditation before bed',
      'Day 4: Take magnesium and dim lights 2 hours before sleep',
      'Day 5: Do a recovery day. Foam rolling, stretching, sauna if available',
      'Day 6: Journal for 10 minutes about what\'s stressing you',
      'Day 7: Sleep in. No alarm. See how your body feels.',
    ],
    ogTitle: "I'm The Restless Achiever",
    seoDescription: "The Restless Achiever wellness archetype. Strong body but low recovery. Learn how fixing sleep and stress can help you get the gains you're chasing.",
  },
  {
    slug: 'sleep-seeker',
    name: 'The Sleep Seeker',
    tagline: 'Everything improves when you sleep better',
    description:
      "Sleep is your biggest opportunity right now. Whether it's trouble falling asleep, waking up groggy, or running on caffeine, poor rest is likely affecting your energy, mood, and health more than you realise. The good news? Sleep is one of the most fixable pillars, and when you get it right, everything else improves almost automatically.",
    strengths: ['Awareness that something needs to change', 'Resilience despite poor rest', 'Openness to improvement'],
    growthAreas: ['Sleep hygiene', 'Evening routines', 'Reducing stimulants and screens'],
    topArticles: ['how-to-fix-your-sleep-in-7-days', 'sleep-stress-skin-wellness-triangle'],
    alsoRecommended: ['meditation-for-beginners-start-5-minutes', '8-adaptogens-that-actually-work', 'toxin-free-living-where-to-start'],
    quickStartPlan: [
      'Day 1: Set a fixed wake time. Same time every day, including weekends',
      'Day 2: No caffeine after 12 PM',
      'Day 3: Create a 30-minute wind-down routine (dim lights, no screens)',
      'Day 4: Make your bedroom cooler and darker',
      'Day 5: Try magnesium glycinate before bed',
      'Day 6: Morning sunlight within 30 minutes of waking',
      'Day 7: Assess. Are you falling asleep faster? Track it.',
    ],
    ogTitle: "I'm The Sleep Seeker",
    seoDescription: 'The Sleep Seeker wellness archetype. Your biggest wellness opportunity is better sleep. Get a 7-day plan to improve your rest and energy levels.',
  },
  {
    slug: 'stress-survivor',
    name: 'The Stress Survivor',
    tagline: 'Carrying more than you need to',
    description:
      "You're getting through each day, but stress is running the show. Whether it's work pressure, constant mental chatter, or just never feeling truly relaxed, chronic stress is draining your energy and likely affecting your sleep, digestion, and even your skin. Building a simple, non-negotiable stress practice is the single highest-impact change you can make right now.",
    strengths: ['Resilience under pressure', 'Ability to keep going', 'Self-awareness about stress levels'],
    growthAreas: ['Daily stress management practice', 'Setting boundaries', 'Nervous system regulation'],
    topArticles: ['8-adaptogens-that-actually-work', 'walking-for-health-underrated-exercise'],
    alsoRecommended: ['meditation-for-beginners-start-5-minutes', 'meditation-cortisol-stillness-heals-skin', 'sleep-stress-skin-wellness-triangle'],
    quickStartPlan: [
      'Day 1: 5 minutes of box breathing (4-4-4-4), morning and evening',
      'Day 2: Walk for 20 minutes with no phone, no music',
      'Day 3: Write down your top 3 stressors. Just name them',
      'Day 4: Try an adaptogen tea (ashwagandha or reishi)',
      "Day 5: Say no to one thing you'd normally agree to",
      'Day 6: 10-minute guided meditation before bed',
      'Day 7: Spend 1 hour doing something purely for enjoyment',
    ],
    ogTitle: "I'm The Stress Survivor",
    seoDescription: 'The Stress Survivor wellness archetype. Stress is your biggest wellness bottleneck. Get a practical 7-day plan to build calm and resilience.',
  },
  {
    slug: 'fresh-starter',
    name: 'The Fresh Starter',
    tagline: 'Every expert was once a beginner',
    description:
      "You're right at the start, and that's a powerful place to be. Most pillars, like movement, sleep, stress, and nutrition, have significant room for improvement, but that means even small changes will create noticeable results. Don't try to overhaul everything at once. Pick one pillar, build one habit, and let momentum do the rest.",
    strengths: ['Clean slate', 'High potential for rapid improvement', 'Curiosity about health'],
    growthAreas: ['Building consistent habits', 'Starting with nutrition basics', 'Adding daily movement'],
    topArticles: ['complete-guide-ancestral-eating', 'walking-for-health-underrated-exercise'],
    alsoRecommended: ['how-to-fix-your-sleep-in-7-days', 'high-protein-breakfasts-without-grains', 'meditation-for-beginners-start-5-minutes', 'morning-mobility-routine-15-min'],
    quickStartPlan: [
      'Day 1: Eat a real breakfast. Eggs, avocado, or yoghurt with fruit',
      "Day 2: Walk for 15 minutes outside. That's it",
      'Day 3: Go to bed 30 minutes earlier than usual',
      'Day 4: Cook one meal from scratch using whole ingredients',
      'Day 5: Walk again. Aim for 20 minutes today',
      'Day 6: Try 3 minutes of deep breathing before bed',
      'Day 7: Write down how you feel compared to last week',
    ],
    ogTitle: "I'm The Fresh Starter",
    seoDescription: "The Fresh Starter wellness archetype. You're at the beginning with huge potential. Get a simple 7-day plan to start building real habits.",
  },
];

export function getArchetype(slug: string): Archetype | undefined {
  return archetypes.find((a) => a.slug === slug);
}
