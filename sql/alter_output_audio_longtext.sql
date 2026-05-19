-- PCM16 base64 常超过 TEXT(64KB)，批量音频结果需 LONGTEXT
ALTER TABLE batch_job_result
    MODIFY COLUMN outputAudio LONGTEXT NULL COMMENT '输出音频JSON {format,data}';

ALTER TABLE conversation_message
    MODIFY COLUMN outputAudio LONGTEXT NULL COMMENT '输出音频JSON';
