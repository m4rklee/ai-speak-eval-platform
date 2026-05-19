# AI 口语评测平台（Lite）

面向语音与听力场景的大模型评测 Web 平台：口语多维评测、听力选择题评测、模型库管理、多模型对比与 Prompt 实验。

> 精简版：已移除 AI 对话、独立语音工作台、批量评测等页面；数据集不随仓库分发，见 [`data/README.md`](data/README.md)。

## 功能

| 模块 | 说明 |
|------|------|
| **口语评测** | 语音（MultiPA + APG-MOS）、内容（LLM Judge 三维）、综合评测 |
| **听力评测** | 北极星 2201 题库，音频模型四选一，准确率统计 |
| **模型库** | OpenRouter / AiHubMix 同步与筛选 |
| **模型对比** | 多模型并排对话与人工偏好 |
| **Prompt Lab** | 单模型多提示词变体对比 |
| **场景管理** | 系统预设与自定义场景 |
| **用户管理** | 管理员用户列表（需 admin 角色） |

## 技术栈

- **前端**：Vue 3 + TypeScript + Vite + Ant Design Vue（默认 `:6006`）
- **后端**：FastAPI + SQLAlchemy + Redis Session（默认 `:6008`）
- **模型**：OpenRouter、AiHubMix（可配置 HTTP 代理）

## 快速开始

### 1. 依赖

- Python 3.10+、Node.js 18+
- MySQL、Redis
- 口语语音评测需 MultiPA / APG-MOS 常驻服务（见 `scripts/eval-daemons.sh`）

### 2. 数据库

```bash
mysql -u root -p < sql/create_table.sql
# 按需执行 sql/ 下其他迁移脚本
```

### 3. 后端

```bash
cd python-backend
cp .env.example .env
# 编辑 .env：数据库、Redis、OPENROUTER_API_KEY、AIHUBMIX_API_KEY 等
pip install -r requirements.txt
```

### 4. 本地数据（仓库不含数据集）

```bash
# 内容评测题库（示例）
mkdir -p data/questiontext
# 将题目 .txt 放入 data/questiontext/

# 听力评测：在 .env 设置 LISTEN_EVAL_PACKAGE_DIR
```

详见 [`data/README.md`](data/README.md)。

### 5. 启动

```bash
# 项目根目录
bash scripts/restart-dev.sh all
```

- 前端：http://localhost:6006  
- 后端 API：http://localhost:6008  
- 健康检查：http://localhost:6008/api/health  

仅改前端时可执行：`bash scripts/restart-dev.sh frontend`

## 环境变量要点

| 变量 | 说明 |
|------|------|
| `OPENROUTER_API_KEY` | OpenRouter 调用 |
| `OPENROUTER_HTTP_PROXY` | 可选，如 `http://127.0.0.1:7890` |
| `AIHUBMIX_API_KEY` | AiHubMix 调用 |
| `LISTEN_EVAL_PACKAGE_DIR` | 听力评测包路径 |
| `UNIFIED_EVAL_*` / `MULTIPA_*` / `APG_MOS_*` | 口语语音评测 daemon |

完整说明见 `python-backend/.env.example` 与 [`PROJECT.md`](PROJECT.md)。

## 目录结构

```
├── frontend/          # Vue 前端
├── python-backend/    # FastAPI 后端
├── data/              # 本地题库（gitignore，见 data/README.md）
├── sql/               # 数据库脚本
└── scripts/           # 启动与评测 daemon 脚本
```

## 开发说明

- 默认登录与权限见 `sql/create_table.sql` 种子用户（部署后请修改密码）。
- 推送代码前确认未提交 `.env` 与 `data/` 下大文件。
- 更完整的架构与 API 说明见 [`PROJECT.md`](PROJECT.md)（部分章节对应完整版，Lite 以本 README 功能表为准）。

## License

Private / 按仓库所有者约定使用。
