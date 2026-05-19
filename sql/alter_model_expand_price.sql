-- 放宽 OpenRouter 模型价格字段范围，避免高价模型同步时报 out of range
alter table model
    modify column inputPrice decimal(20, 10) null comment '输入价格（每百万tokens，美元）',
    modify column outputPrice decimal(20, 10) null comment '输出价格（每百万tokens，美元）';
