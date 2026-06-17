# 大模型口语练习应用能力测试平台

> 一个面向口语练习场景的大模型选型的一站式评测系统。

大模型越来越多地用于口语练习与教学，但常见痛点包括：

- 不同实验评测标准不统一，难以横向比较。
- 语音、内容、听力评测常分散在临时脚本和表格中。
- 从出题、调用模型到生成报告的链路重复搭建成本高。

本项目构建了一个面向口语练习场景的大模型选型的一站式评测系统，用于对比不同模型在语音质量、听力理解和口语表达上的表现。

## 项目功能

- **统一评测流程**: 一站式口语练习能力评测。
- **多维评测得分**: 覆盖发音准确度、流利度、自然度、语法、主题聚焦、回答简洁和听力理解。
- **批量模型评估**: 支持批量评测、进度跟踪和结果导出。
- **对接第三方API平台**: 对接 AiHubMix、OpenRouter 等平台，支持按模态、价格和能力筛选模型。

## 项目演示


## 项目流程

```text
Vue 3 Frontend
      |
      v
Python Backend
      |
      +--> scenario and dataset management
      +--> model provider adapters
      +--> speech evaluation
      +--> content evaluation
      +--> batch jobs
      +--> report export
      |
      v
MySQL / Redis / external model APIs
```

更详细的系统设计见 [PROJECT.md](PROJECT.md)。

## 技术栈

- **前端**: Vue 3, TypeScript, Vite, Pinia, Ant Design Vue
- **后端**: Python, FastAPI-style service structure
- **数据库**: MySQL, Redis
  
## 快速开始

```bash
git clone https://github.com/m4rklee/ai-speak-eval-platform.git
cd ai-speak-eval-platform
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Backend:

```bash
cd python-backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

启动依赖和开发服务可参考：

```text
scripts/ensure-infra.sh
scripts/restart-dev.sh
scripts/eval-daemons.sh
```

## 项目结构

```text
frontend/                # Vue 3 web frontend
python-backend/          # Python backend service
sql/                     # Database schema and migrations
scripts/                 # Dev, infra and evaluation scripts
data/                    # Dataset notes
PROJECT.md               # Architecture and project notes
```
