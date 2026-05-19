-- 为模型表增加 OpenRouter 模态能力字段
alter table model
    add column modality varchar(100) null comment '模态，如 text+image->text' after contextLength,
    add column inputModalities varchar(500) null comment '输入模态（JSON数组字符串）' after modality,
    add column outputModalities varchar(500) null comment '输出模态（JSON数组字符串）' after inputModalities;
