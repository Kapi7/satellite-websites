export interface QuizOption {
  label: string;
  score: number;
}

export interface QuizQuestion {
  id: number;
  pillar: 'movement' | 'sleep' | 'stress' | 'nutrition';
  question: string;
  options: QuizOption[];
}

export const quizQuestions: QuizQuestion[] = [
  // Movement (Q1-Q3)
  {
    id: 1,
    pillar: 'movement',
    question: 'How does your body feel when you wake up?',
    options: [
      { label: 'Loose and ready to move', score: 10 },
      { label: 'A bit stiff but loosens up quickly', score: 7 },
      { label: 'Stiff and achy most mornings', score: 3 },
      { label: "Don't really notice — I go straight to my phone", score: 1 },
    ],
  },
  {
    id: 2,
    pillar: 'movement',
    question: 'How would you describe your weekly movement?',
    options: [
      { label: 'Mix of strength, walking, and mobility', score: 10 },
      { label: 'Regular but mostly one type of exercise', score: 7 },
      { label: 'Occasional walks or light activity', score: 4 },
      { label: 'Mostly sedentary', score: 1 },
    ],
  },
  {
    id: 3,
    pillar: 'movement',
    question: 'How often do you move your body outdoors?',
    options: [
      { label: 'Daily — rain or shine', score: 9 },
      { label: 'A few times a week', score: 7 },
      { label: 'Mostly on weekends', score: 4 },
      { label: 'Rarely', score: 1 },
    ],
  },

  // Sleep (Q4-Q5)
  {
    id: 4,
    pillar: 'sleep',
    question: 'Do you wake up feeling genuinely rested?',
    options: [
      { label: 'Almost every day', score: 10 },
      { label: 'Most days', score: 7 },
      { label: 'Rarely', score: 3 },
      { label: "Can't remember the last time", score: 1 },
    ],
  },
  {
    id: 5,
    pillar: 'sleep',
    question: "What's your evening wind-down like?",
    options: [
      { label: 'Screens off, reading or journaling', score: 10 },
      { label: 'Try to relax but end up scrolling', score: 5 },
      { label: 'Work or shows right until I crash', score: 2 },
      { label: 'I just fall asleep from exhaustion', score: 1 },
    ],
  },

  // Stress (Q6-Q7)
  {
    id: 6,
    pillar: 'stress',
    question: "When something stressful happens, what's your first response?",
    options: [
      { label: 'Pause, breathe, then respond', score: 10 },
      { label: 'Feel anxious but recover within an hour', score: 7 },
      { label: 'It lingers with me all day', score: 3 },
      { label: 'I spiral — it affects everything', score: 1 },
    ],
  },
  {
    id: 7,
    pillar: 'stress',
    question: 'Do you have a regular stress management practice?',
    options: [
      { label: 'Yes — meditation, breathwork, or journaling daily', score: 10 },
      { label: 'Sometimes, when I remember', score: 6 },
      { label: "I've tried things but nothing stuck", score: 3 },
      { label: 'I cope with food, scrolling, or distraction', score: 1 },
    ],
  },

  // Nutrition (Q8-Q10)
  {
    id: 8,
    pillar: 'nutrition',
    question: "What's your typical breakfast?",
    options: [
      { label: 'Eggs, meat, or another protein-forward meal', score: 10 },
      { label: 'Oats, smoothie, or yoghurt', score: 7 },
      { label: 'Cereal, toast, or a pastry', score: 3 },
      { label: 'Skip it — just coffee', score: 1 },
    ],
  },
  {
    id: 9,
    pillar: 'nutrition',
    question: 'How much of your daily food is whole and unprocessed?',
    options: [
      { label: 'Almost everything I eat', score: 10 },
      { label: 'The majority', score: 7 },
      { label: 'About half', score: 4 },
      { label: 'Mostly packaged or processed', score: 1 },
    ],
  },
  {
    id: 10,
    pillar: 'nutrition',
    question: 'Do you eat seasonally or care about where your food comes from?',
    options: [
      { label: "Farmers markets and seasonal eating are my thing", score: 10 },
      { label: 'I try when I can', score: 6 },
      { label: 'Not really', score: 3 },
      { label: 'Never thought about it', score: 1 },
    ],
  },
];

export const pillarMaxScores: Record<string, number> = {
  movement: 29, // 10+10+9
  sleep: 20,    // 10+10
  stress: 20,   // 10+10
  nutrition: 30, // 10+10+10
};
