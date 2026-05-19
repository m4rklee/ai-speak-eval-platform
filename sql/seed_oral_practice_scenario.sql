-- K-12 口语练习示例场景（文本元数据；音频需通过批量页导入或复用已有场景）
INSERT INTO scenario (id, userId, name, description, sourceType, category, itemCount, isDelete)
VALUES (
  'sys-scenario-oral-k12',
  NULL,
  'K-12 口语练习示例',
  '学生音频 → 教师模型回复 → 听力/发音/内容自动评分。导入时请为每条附上 audioData。',
  'system',
  'oral_practice',
  4,
  0
)
ON DUPLICATE KEY UPDATE name = VALUES(name), description = VALUES(description);

INSERT INTO scenario_item (id, scenarioId, prompt, expectedAnswer, category, sortOrder, isDelete)
VALUES
(
  'sys-oral-k12-1',
  'sys-scenario-oral-k12',
  '请用英语回答：你最喜欢的科目是什么？为什么？',
  'My favorite subject is science because I enjoy doing experiments and learning how things work.',
  'speaking',
  0,
  0
),
(
  'sys-oral-k12-2',
  'sys-scenario-oral-k12',
  '请用英语描述你昨天放学后做了什么。',
  'After school yesterday, I finished my homework, played basketball with friends, and had dinner with my family.',
  'speaking',
  1,
  0
),
(
  'sys-oral-k12-3',
  'sys-scenario-oral-k12',
  '请用英语介绍你的好朋友（姓名、性格、共同爱好）。',
  'My best friend is kind and funny. We both like reading and playing video games after class.',
  'speaking',
  2,
  0
),
(
  'sys-oral-k12-4',
  'sys-scenario-oral-k12',
  '请用英语说明如何保持健康（饮食、运动、睡眠）。',
  'To stay healthy, I eat vegetables and fruit, exercise regularly, and get enough sleep every night.',
  'mixed',
  3,
  0
)
ON DUPLICATE KEY UPDATE prompt = VALUES(prompt), expectedAnswer = VALUES(expectedAnswer);
