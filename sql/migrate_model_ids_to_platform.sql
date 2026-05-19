-- 将已有模型 ID 迁移为 openrouter: 前缀（仅处理尚未带前缀的行）
UPDATE model SET id = CONCAT('openrouter:', id), platform = 'openrouter'
WHERE id NOT LIKE '%:%' AND isDelete = 0;
