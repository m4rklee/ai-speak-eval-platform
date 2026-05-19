-- 语音评测相关字段

ALTER TABLE conversation_message
    ADD COLUMN outputAudio TEXT NULL COMMENT '输出音频JSON {format,data}' AFTER reasoning,
    ADD COLUMN outputModality VARCHAR(30) NULL COMMENT '输出模态 text/audio/text+audio' AFTER outputAudio;

ALTER TABLE scenario_item
    ADD COLUMN inputType VARCHAR(20) NOT NULL DEFAULT 'text' COMMENT 'text/audio/text+audio' AFTER category,
    ADD COLUMN audioData MEDIUMTEXT NULL COMMENT '输入音频base64' AFTER inputType,
    ADD COLUMN audioFormat VARCHAR(20) NULL COMMENT '音频格式 wav/mp3等' AFTER audioData,
    ADD COLUMN audioFileName VARCHAR(255) NULL COMMENT '原始文件名' AFTER audioFormat;

ALTER TABLE batch_job
    ADD COLUMN outputModality VARCHAR(30) NOT NULL DEFAULT 'text' COMMENT '期望输出模态' AFTER concurrency,
    ADD COLUMN globalPrompt TEXT NULL COMMENT '批量共用提示词' AFTER outputModality;

ALTER TABLE batch_job_result
    ADD COLUMN outputAudio TEXT NULL COMMENT '输出音频JSON' AFTER outputContent,
    ADD COLUMN outputModality VARCHAR(30) NULL COMMENT '实际输出模态' AFTER outputAudio,
    ADD COLUMN evalScore DECIMAL(5, 2) NULL COMMENT '评测分数预留' AFTER score,
    ADD COLUMN evalDetail TEXT NULL COMMENT '评测详情JSON预留' AFTER evalScore;
