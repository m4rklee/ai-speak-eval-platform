-- K-12 口语练习评测：任务配置与评分阶段

ALTER TABLE batch_job
    ADD COLUMN jobType VARCHAR(30) NOT NULL DEFAULT 'batch_audio' COMMENT 'batch_audio|oral_practice|generate_only|score_only' AFTER globalPrompt,
    ADD COLUMN systemPrompt TEXT NULL COMMENT '口语练习 system 提示词' AFTER jobType,
    ADD COLUMN userMessageMode VARCHAR(30) NOT NULL DEFAULT 'text_plus_audio' COMMENT 'audio_only|text_plus_audio' AFTER systemPrompt,
    ADD COLUMN evalConfig JSON NULL COMMENT '评分配置 JSON' AFTER userMessageMode;
