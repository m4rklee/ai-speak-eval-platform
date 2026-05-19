# 本地数据目录（不纳入 Git）

本目录用于存放评测题库等数据，**不会上传到 GitHub**。克隆仓库后请自行准备。

## 内容评测题库

将题目文本放入 `questiontext/`，文件名如 `00174.txt`（与内容评测 stem 匹配）。

默认路径：项目根目录 `data/questiontext/`（与 `python-backend` 中 `content_eval_question_dir` 一致）。

## 听力评测（北极星 2201）

在 `python-backend/.env` 中配置：

```bash
LISTEN_EVAL_PACKAGE_DIR=/你的路径/北极星2201评测包
```

需包含 `benchmark.json` 与音频资源目录。未配置时「听力评测」页会显示题库未就绪。
