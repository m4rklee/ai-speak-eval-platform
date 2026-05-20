# AI 口语评测平台

> 面向口语练习与模型选型的一站式评测系统：统一评测标准、多维打分、多模型横向对比。

---

## 背景 📖

### 要解决什么问题

大模型越来越多地用于口语练习与教学，但常见痛点是：

- **标准不统一**：不同实验难以在同一套尺度上对比；
- **能力难横向比**：语音、内容、听力往往分散在表格和临时脚本里；
- **链路太长**：从出题、调用模型到出报告，重复搭建成本高。

本项目将 **数据集建设、评测维度设计、模型调用与结果分析** 收敛到同一 Web 产品，教研与算法同学用浏览器即可完成实验。

### 建设亮点

| 方向 | 说明 |
|------|------|
| **平台规划** | 从 0 到 1 落地口语、听力、模型库、多模型对比、Prompt 实验等模块 |
| **评测维度** | 发音、流利、自然度、语法、主题聚焦、回答简洁、听力理解等；结合专用语音模型与大模型 Judge |
| **数据建设** | 公开数据 **3000+ 条**；约 **40%** 音频合成增强发音与流利度档位；**200 条** 真实对话补充 |
| **模型整合** | 接入 AiHubMix、OpenRouter，支持批量评测、进度跟踪与报告导出 |
| **完整链路** | 题目音频 → 模型生成回答 → 语音 + 内容综合评测，支持分步或一站式流水线 |

### 评测体系与数据

- **语音侧**：发音准确性、流利度、韵律与自然度  
- **内容侧**：语法、主题聚焦、回答简洁清晰  
- **听力侧**：听音理解准确率  
- **综合**：同一作答同时输出语音与内容评价  

技术栈：Vue 3 + FastAPI + MySQL + Redis；语音评测对接 MultiPA、APG-MOS 等。更细的架构见 [`PROJECT.md`](PROJECT.md)。

---

## 功能 ✨

| 模块 | 说明 |
|------|------|
| 🎙️ **口语评测** | 回复生成、语音评测、内容评测、综合评测与一站式流水线 |
| 🎧 **听力评测** | 听音选题、准确率统计、抽题与结果导出 |
| 📚 **模型库** | 双平台模型同步，按模态、价格等筛选 |
| ⚖️ **模型对比** | 多模型并排生成，支持人工偏好与横向比较 |
| 🧪 **Prompt Lab** | 单模型多提示词变体对比与实验记录 |
| 🗂️ **场景管理** | 系统预设 + 自定义场景，支持 JSON 导入题目 |
| 👥 **用户管理** | 多用户与管理员权限 |

**典型流程**

```text
题目音频 → 模型生成回答 → 语音与内容维度评分 → 对比表 / 导出报告
```

---

## 用法 🚀

### 环境要求 🛠️

- Python 3.10+、Node.js 18+
- MySQL、Redis
- 口语 **语音评测** 需本机启动 MultiPA / APG-MOS（`scripts/eval-daemons.sh`）

### 克隆与依赖 📦

```bash
git clone https://github.com/m4rklee/ai-speak-eval-platform.git
cd ai-speak-eval-platform

cd python-backend && pip install -r requirements.txt && cp .env.example .env
cd ../frontend && npm install
```

### 数据库与本地数据 🗄️

```bash
# 项目根目录
mysql -u root -p < sql/create_table.sql
```

评测数据 **不随仓库发布**，请本地准备：

- 内容评测：将 `*.txt` 放入 `data/questiontext/`
- 听力评测：在 `.env` 中设置 `LISTEN_EVAL_PACKAGE_DIR`

详见 [`data/README.md`](data/README.md)。

### 配置与启动 ▶️

编辑 `python-backend/.env`（API Key、数据库、Redis、代理等，见 `.env.example`），然后：

```bash
# 项目根目录：启动 MariaDB/Redis、前后端与评测 daemon
bash scripts/restart-dev.sh all
```

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:6006 |
| 后端 | http://localhost:6008 |
| 健康检查 | http://localhost:6008/api/health |

### 登录使用 👤

1. 浏览器打开前端，注册或使用 `sql/create_table.sql` 中的种子账号登录  
2. 在 **模型库** 同步模型后，进入各评测页提交任务  
3. 管理员可进入 **用户管理**  

> 生产环境请修改默认密码，勿将 `.env` 提交到 Git。

---

## 相关链接 🔗

- **代码仓库**：https://github.com/m4rklee/ai-speak-eval-platform  
- **技术文档**：[`PROJECT.md`](PROJECT.md)
