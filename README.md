# AI 口语评测平台

面向 **语音 / 听力 / 大模型** 的统一评测 Web 平台，支持口语多维打分、听力准确率评测、模型库管理与对比实验。

---

## 一、背景 📖

在口语教学与模型选型场景中，往往需要同时评估：

- **语音质量**（发音、流利度、自然度等）
- **内容质量**（语法、主题、表达简洁等）
- **听力理解**（听音频选答案、统计准确率）
- **多模型差异**（并排对比、Prompt 变体实验）

本平台将上述能力整合为一套前后端分离的评测系统，通过 **OpenRouter / AiHubMix** 调用各类多模态模型，并对接 **MultiPA + APG-MOS** 等语音评测引擎。

**说明**
- **数据集不随仓库发布**：内容评测题库、听力评测包需在本地自行配置，见 [`data/README.md`](data/README.md)

**技术栈概览**

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 · TypeScript · Vite · Ant Design Vue |
| 后端 | FastAPI · SQLAlchemy · Redis Session |
| 数据 | MySQL · Redis |
| 模型 | OpenRouter · AiHubMix（支持 HTTP 代理） |

---

## 二、功能 ✨

| 模块 | 说明 |
|------|------|
| 🎙️  **口语评测** | 语音评测、内容评测、综合评测 |
| 🎧  **听力评测** | 支持随机抽题、进度展示、准确率与明细导出 |
| 📚  **模型库** | 双平台模型同步，按输入/输出模态、价格等筛选 |
| ⚖️ **模型对比** | 最多 8 个模型并排生成，支持图文音附件与人工偏好评分 |
| 🧪  **Prompt Lab** | 单模型多提示词变体对比，可自动生成变体并记录实验结果 |
| 🗂️  **场景管理** | 系统预设场景 + 自定义场景，支持 JSON 导入题目 |
| 👥  **用户管理** | 管理员查看与管理用户（需 `admin` 角色） |

---

## 三、使用方式 🚀

### 3.1 环境要求 🛠️

- Python 3.10+
- Node.js 18+
- MySQL、Redis
- 口语 **语音评测** 需本机启动 MultiPA / APG-MOS 常驻服务（`scripts/eval-daemons.sh`）

### 3.2 克隆与依赖 📦

```bash
git clone https://github.com/m4rklee/ai-speak-eval-platform.git
cd ai-speak-eval-platform

# 后端
cd python-backend
pip install -r requirements.txt
cp .env.example .env   # 按需修改配置

# 前端
cd ../frontend
npm install
```

### 3.3 初始化数据库 🗄️

```bash
# 在项目根目录
mysql -u root -p < sql/create_table.sql
# 按需执行 sql/ 目录下其他迁移脚本
```

### 3.4 配置本地数据 📁

仓库 **不包含** 评测数据集，请本地准备：

```bash
# 内容评测：题目文本
mkdir -p data/questiontext
# 将 *.txt 放入 data/questiontext/

# 听力评测：在 python-backend/.env 中设置
# LISTEN_EVAL_PACKAGE_DIR=/你的路径/北极星2201评测包
```

详细说明见 [`data/README.md`](data/README.md)。

### 3.5 配置环境变量 🔑

编辑 `python-backend/.env`，至少配置：

| 变量 | 说明 |
|------|------|
| `OPENROUTER_API_KEY` | OpenRouter API Key |
| `AIHUBMIX_API_KEY` | AiHubMix API Key |
| `DB_*` / `REDIS_*` | 数据库与 Redis 连接 |
| `OPENROUTER_HTTP_PROXY` | 可选，如 `http://127.0.0.1:7890` |
| `LISTEN_EVAL_PACKAGE_DIR` | 听力评测包本地路径 |
| `UNIFIED_EVAL_*` / `MULTIPA_*` / `APG_MOS_*` | 口语语音评测 daemon 相关 |

完整项见 `python-backend/.env.example`。

### 3.6 启动服务 ▶️

```bash
# 项目根目录
bash scripts/restart-dev.sh all
```

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:6006 |
| 后端 API | http://localhost:6008 |
| 健康检查 | http://localhost:6008/api/health |

常用命令：

```bash
bash scripts/restart-dev.sh frontend   # 仅重启前端
bash scripts/restart-dev.sh backend    # 仅重启后端
bash scripts/restart-dev.sh daemons    # 仅管理评测 daemon
```

### 3.7 登录与使用 👤

1. 浏览器打开前端地址，注册或使用种子账号登录（见 `sql/create_table.sql`）
2. 在 **模型库** 同步模型后，进入各评测页面选择模型并提交任务
3. 管理员可访问 **用户管理** 页面

> 部署到生产环境后请修改默认密码，且勿将 `.env` 提交到 Git。

### 3.8 目录结构 📂

```
├── frontend/          # Vue 前端
├── python-backend/    # FastAPI 后端
├── data/              # 本地题库（gitignore）
├── sql/               # 数据库脚本
└── scripts/           # 启动与 daemon 脚本
```

完整的架构与 API 文档见 [`PROJECT.md`](PROJECT.md)。                                              
