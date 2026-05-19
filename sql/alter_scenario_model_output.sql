-- 场景项预置待评文本（批量文本评分 / score_only 任务）
ALTER TABLE scenario_item
    ADD COLUMN modelOutput TEXT NULL COMMENT '待评模型回复文本（score_only 导入）' AFTER expectedAnswer;
