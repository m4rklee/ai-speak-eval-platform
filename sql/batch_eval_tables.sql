-- 批量评测相关表

-- 场景/数据集
create table if not exists scenario
(
    id           varchar(36) primary key comment '场景ID',
    userId       bigint       null comment '用户ID，null表示系统预设',
    name         varchar(200) not null comment '场景名称',
    description  varchar(1000) null comment '场景描述',
    sourceType   varchar(20)  not null comment '来源：system/custom',
    category     varchar(100) null comment '分类',
    itemCount    int          not null default 0 comment '用例数量',
    createTime   datetime     not null default CURRENT_TIMESTAMP comment '创建时间',
    updateTime   datetime     not null default CURRENT_TIMESTAMP on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete     tinyint      not null default 0 comment '逻辑删除',
    index idx_user (userId, isDelete),
    index idx_source (sourceType, isDelete)
) comment '测试场景表' collate = utf8mb4_unicode_ci;

-- 场景用例
create table if not exists scenario_item
(
    id             varchar(36) primary key comment '用例ID',
    scenarioId     varchar(36)  not null comment '场景ID',
    prompt         text         not null comment '提示词',
    expectedAnswer text         not null comment '期望答案',
    category       varchar(100) null comment '分类',
    sortOrder      int          not null default 0 comment '排序',
    createTime     datetime     not null default CURRENT_TIMESTAMP comment '创建时间',
    updateTime     datetime     not null default CURRENT_TIMESTAMP on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete       tinyint      not null default 0 comment '逻辑删除',
    index idx_scenario (scenarioId, sortOrder, isDelete)
) comment '场景用例表' collate = utf8mb4_unicode_ci;

-- 批量任务
create table if not exists batch_job
(
    id              varchar(36) primary key comment '任务ID',
    userId          bigint       not null comment '用户ID',
    scenarioId      varchar(36)  not null comment '场景ID',
    models          json         not null comment '模型列表',
    status          varchar(20)  not null default 'pending' comment 'pending/running/completed/failed/cancelled',
    totalTasks      int          not null default 0 comment '总子任务数',
    completedTasks  int          not null default 0 comment '已完成数',
    failedTasks     int          not null default 0 comment '失败数',
    concurrency     int          not null default 3 comment '并发数',
    errorSummary    varchar(1000) null comment '错误摘要',
    startedAt       datetime     null comment '开始时间',
    finishedAt      datetime     null comment '结束时间',
    createTime      datetime     not null default CURRENT_TIMESTAMP comment '创建时间',
    updateTime      datetime     not null default CURRENT_TIMESTAMP on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete        tinyint      not null default 0 comment '逻辑删除',
    index idx_user_created (userId, createTime desc, isDelete),
    index idx_scenario (scenarioId, isDelete),
    index idx_status (status, isDelete)
) comment '批量评测任务表' collate = utf8mb4_unicode_ci;

-- 批量任务结果
create table if not exists batch_job_result
(
    id              varchar(36) primary key comment '结果ID',
    jobId           varchar(36)  not null comment '任务ID',
    scenarioItemId  varchar(36)  not null comment '用例ID',
    modelName       varchar(100) not null comment '模型名称',
    prompt          text         not null comment '提示词',
    expectedAnswer  text         not null comment '期望答案',
    outputContent   text         null comment '模型输出',
    status          varchar(20)  not null comment 'success/error',
    errorMessage    varchar(2000) null comment '错误信息',
    responseTimeMs  int          null comment '响应时间毫秒',
    inputTokens     int          null comment '输入Token',
    outputTokens    int          null comment '输出Token',
    cost            decimal(10, 6) null comment '成本USD',
    score           decimal(5, 2) null comment '评分预留',
    createTime      datetime     not null default CURRENT_TIMESTAMP comment '创建时间',
    updateTime      datetime     not null default CURRENT_TIMESTAMP on update CURRENT_TIMESTAMP comment '更新时间',
    isDelete        tinyint      not null default 0 comment '逻辑删除',
    index idx_job (jobId, isDelete),
    index idx_job_model (jobId, modelName, isDelete)
) comment '批量评测结果表' collate = utf8mb4_unicode_ci;

-- 用户模型使用统计
create table if not exists user_model_stat
(
    id                 bigint auto_increment primary key comment 'ID',
    userId             bigint         not null comment '用户ID',
    modelName          varchar(100)   not null comment '模型名称',
    callCount          bigint         not null default 0 comment '调用次数',
    totalInputTokens   bigint         not null default 0 comment '累计输入Token',
    totalOutputTokens  bigint         not null default 0 comment '累计输出Token',
    totalCost          decimal(12, 6) not null default 0 comment '累计成本USD',
    lastUsedAt         datetime       null comment '最后使用时间',
    createTime         datetime       not null default CURRENT_TIMESTAMP comment '创建时间',
    updateTime         datetime       not null default CURRENT_TIMESTAMP on update CURRENT_TIMESTAMP comment '更新时间',
    unique key uk_user_model (userId, modelName)
) comment '用户模型使用统计表' collate = utf8mb4_unicode_ci;

-- 模型表扩展：批量调用次数（若已存在可忽略报错）
-- alter table model add column batchCallCount bigint not null default 0 comment '批量评测调用次数';
