export const DEFAULT_TEACHER_SYSTEM_PROMPT = `You are a friendly teacher having a casual conversation with a middle school student. Answer the question in this audio naturally, using vocabulary and explanations appropriate for middle school level. Provide a thoughtful and brief response - about 2-3 sentences or 10-20 seconds when spoken. Avoid using bullet points, numbered lists unless specifically asked for.`

export const DEFAULT_EVAL_CONFIG = {
  listening: { enabled: true, mode: 'normalized_match' },
  pronunciation: {
    enabled: true,
    provider: 'unified',
    baseUrl: '',
    refTextFrom: 'output_content',
  },
  contentJudge: {
    enabled: true,
    judgeModel: 'openrouter:openai/gpt-4o',
    maxScore: 5,
    rubric:
      'Evaluate whether the model response appropriately addresses the student audio for middle-school oral practice. Score 1-5 for content quality and alignment with the reference answer.',
  },
  weights: { listening: 0.35, pronunciation: 0.35, content: 0.3 },
}
