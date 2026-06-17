# AI Speak Eval Platform

> A web-based evaluation platform for spoken-language practice models, speech scoring, listening tasks, and multi-model comparison.

AI Speak Eval Platform 是一个面向口语练习与模型选型的一站式评测系统。项目将数据集建设、评测维度设计、模型调用、批量任务、结果分析和报告导出收敛到同一 Web 产品，用于对比不同模型在口语、听力和内容生成场景中的表现。

## Highlights

- **Unified evaluation workflow**: 统一口语、听力、内容质量和多模型对比流程。
- **Multi-dimensional scoring**: 覆盖发音、流利度、自然度、语法、主题聚焦、回答简洁和听力理解。
- **Batch model evaluation**: 支持批量评测、进度跟踪和结果导出。
- **Model library**: 对接 AiHubMix、OpenRouter 等平台，按模态、价格和能力筛选模型。
- **Prompt experiments**: 支持围绕口语练习任务进行 prompt 与模型效果对比。
- **Frontend + backend separation**: Vue 3 前端与 Python backend 分离，便于迭代。

## Background

大模型越来越多地用于口语练习与教学，但常见痛点包括：

- 不同实验评测标准不统一，难以横向比较。
- 语音、内容、听力评测常分散在临时脚本和表格中。
- 从出题、调用模型到生成报告的链路重复搭建成本高。

本项目通过平台化方式沉淀评测数据、模型结果和分析报告。

## Architecture

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

## Features

| Module | Description |
|---|---|
| **Speaking Evaluation** | 回复生成、语音评测、内容评测、综合评测与一站式流水线。 |
| **Listening Evaluation** | 听音选题、准确率统计、抽题与结果导出。 |
| **Model Library** | 双平台模型同步，按模态、价格、上下文等维度筛选。 |
| **Model Comparison** | 多模型并排生成，支持人工偏好与横向比较。 |
| **Batch Jobs** | 批量调用模型并追踪评测进度。 |
| **Report Export** | 对评测结果做统计分析和导出。 |

## Tech Stack

- **Frontend**: Vue 3, TypeScript, Vite, Pinia, Ant Design Vue
- **Backend**: Python, FastAPI-style service structure
- **Database**: MySQL, Redis
- **Model Providers**: AiHubMix, OpenRouter and compatible APIs
- **Speech Evaluation**: MultiPA, APG-MOS and related scoring services
- **Tooling**: SQL migrations, shell scripts, OpenAPI type generation

## Quick Start

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

## Usage

典型流程：

1. 在模型库同步并配置待评测模型。
2. 创建口语或听力评测场景。
3. 导入题目、音频或模型输出。
4. 启动批量评测任务。
5. 查看多维评分、横向对比和导出结果。

## Project Structure

```text
frontend/                # Vue 3 web frontend
python-backend/          # Python backend service
sql/                     # Database schema and migrations
scripts/                 # Dev, infra and evaluation scripts
data/                    # Dataset notes
PROJECT.md               # Architecture and project notes
```

## Notes

- 不同语音评分模型和大模型 judge 的尺度可能不一致，需要结合人工抽检校准。
- 真实业务使用前应明确数据授权、音频隐私和模型调用成本。
- 部分外部模型平台需要单独配置 API Key。

## Roadmap

- Add more reproducible public benchmark subsets.
- Improve scoring calibration and human review workflow.
- Add dashboard-level model ranking reports.
- Add deployment guide for long-running evaluation jobs.
