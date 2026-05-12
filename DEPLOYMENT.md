# Deployment Guide

## 1. 环境要求

- Python **≥ 3.10**

## 2. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

> `rembg[cpu]` 会拉取 `onnxruntime`（约 18 MB），首次运行时还会自动下载 U2Net 模型（约 176 MB），请确保网络畅通。

## 3. GCP 项目配置

### 3.1 启用所需 API

```bash
gcloud config set project YOUR_PROJECT_ID

gcloud services enable aiplatform.googleapis.com
```

### 3.2 配置 ADC 鉴权

**本地开发：**

```bash
gcloud auth application-default login
```

### 3.3 配置 .env 环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入你的项目信息：

```
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=global
```


## 4. 运行

```bash
PYTHONPATH=src python -m picut.cli run ./input ./output --categories talent_node,ui_frame
```

常用选项：

| 选项 | 说明 |
|------|------|
| `--categories` | 类别过滤，逗号分隔（`talent_node` / `ui_frame`） |
| `--dry-run` | 只检测，不抠图，用于验证检测效果 |
| `--redetect` | 忽略缓存，重新调用 API 检测；旧结果自动备份为带时间戳的文件 |
| `--resume` | 跳过已完成的图标，断点续跑 |
| `--matting` | `auto`（默认）/ `rembg` / `magenta` |
