-- 模型表：平台、发布时间；扩展主键长度以支持 platform:vendor_id
ALTER TABLE model MODIFY COLUMN id VARCHAR(200) NOT NULL COMMENT '模型ID，格式 platform:vendorModelId';

ALTER TABLE model ADD COLUMN platform VARCHAR(20) NOT NULL DEFAULT 'openrouter' COMMENT '模型平台 openrouter/aihubmix' AFTER id;
ALTER TABLE model ADD COLUMN releasedAt DATETIME NULL COMMENT '模型发布时间' AFTER platform;
ALTER TABLE model ADD COLUMN modelType VARCHAR(30) NULL COMMENT '模型类型 llm/tts/stt等' AFTER releasedAt;
