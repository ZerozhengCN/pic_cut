# pic_cut

游戏 UI 截图批量图标提取工具。把一堆游戏截图丢进去，自动检测里面的图标和 UI 装饰元素，用 nano-banana (Gemini 3.1 Flash Image) 重新渲染并抠成透明背景的 1024×1024 PNG。

## 它能做什么

- **输入**：一个文件夹的游戏截图（PNG/JPG/WEBP，常见 2560×1440）
- **输出**：每张截图对应一个子文件夹，里面是抠好的透明 PNG，按类别命名：`talent_node_01.png`、`ui_frame_03.png` 等
- **附带**：每张截图同时生成 `_overlay.png`（带检测框的调试图）和 `_detection.json`（检测原始结果）

适用场景：游戏 UI 资源参考、素材库重建、二创设计参考。

> ⚠️ 这是**从渲染像素重建**，不是真正的原始资源提取。如果能拿到游戏安装文件，AssetStudio 之类的工具能直接导出原图，那才是"完全还原"。本工具适用于拿不到原始资源的场景。

## 架构

```
input/screenshot.png
    │
    ├─► [1] detect.py     Gemini 3.1 Pro 视觉检测 → bbox + 类别 JSON
    │       └── 输出 _detection.json + _overlay.png（debug）
    │
    ├─► [2] crop.py       PIL 按 bbox + 8% padding 裁剪
    │
    ├─► [3] extract.py    nano-banana 重新渲染图标到白底 1024×1024
    │
    ├─► [4] matte.py      rembg (U2Net) 本地抠图
    │       └── 兜底：alpha 覆盖率过低时切 magenta 色键路径
    │
    └─► output/<stem>/talent_node_01.png ...
```

**为什么需要本地抠图**：nano-banana 不支持透明背景输出，所以先让它生成在纯白（或品红）背景上，再用 `rembg` 在本地做 alpha matting。`auto` 模式下，如果 rembg 抠出来的 alpha 覆盖率 < 5%，会自动重试用 #FF00FF 背景 + 色键作为兜底。

## 模块划分

| 文件 | 职责 |
|------|------|
| `client.py` | Vertex AI 客户端工厂，ADC 鉴权，硬编码默认 project/location |
| `config.py` | `RunConfig` dataclass + 默认模型常量 |
| `retry.py` | tenacity 包装，处理 429/503/5xx 指数退避 |
| `log.py` | rich 控制台输出 + JSONL run log + resume 索引 |
| `detect.py` | Gemini 视觉检测 prompt + JSON 解析 + bbox 像素反归一化 |
| `crop.py` | PIL 裁剪 + padding + 越界 clamp |
| `overlay.py` | 在原图上画 bbox + 标签（talent_node 黄、ui_frame 青） |
| `extract.py` | nano-banana 调用，白底/品红底两套 prompt |
| `matte.py` | rembg U2Net + magenta 色键兜底 + 1024 居中 padding |
| `pipeline.py` | 单截图编排，进度输出，resume 跳过已完成 |
| `cli.py` | Typer 入口，三个子命令：`run` / `detect` / `estimate` |

## 安装

```bash
cd /home/zeroxxzheng/pic_cut

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

依赖里 `rembg[cpu]` 会拉 `onnxruntime`（约 18MB）。Python ≥ 3.10。

### 鉴权

工具走 Vertex AI + ADC（Application Default Credentials）。云主机自带元数据鉴权，无需手动配 key。

默认 project / location 已硬编码在 [src/picut/client.py](src/picut/client.py)：

```python
DEFAULT_PROJECT  = "zero-normal-test-project"
DEFAULT_LOCATION = "global"
```

需要切别的项目时设环境变量覆盖：

```bash
export GOOGLE_CLOUD_PROJECT=other-project
export GOOGLE_CLOUD_LOCATION=us-central1
```

## 使用

```bash
# 把截图放进 input/
cp ~/your_screenshot.png input/

# 跑前估算成本（不调 API）
PYTHONPATH=src python -m picut.cli estimate ./input

# 单图检测调试（只生成 overlay + json，省钱验 prompt）
PYTHONPATH=src python -m picut.cli detect ./input/foo.png

# 全量运行
PYTHONPATH=src python -m picut.cli run ./input ./output
```

### 常用选项

```bash
PYTHONPATH=src python -m picut.cli run ./input ./output \
    --categories talent_node,ui_frame \         # 类别过滤
    --padding 0.08 \                            # 裁剪边距（占 bbox 比例）
    --matting auto \                            # auto | rembg | magenta
    --concurrency 4 \                           # 并发（暂未启用，预留）
    --detect-model gemini-3.1-pro-preview \     # 检测模型
    --extract-model gemini-3.1-flash-image-preview \  # 抠图/重渲染模型
    --max-icons-per-shot 100 \                  # 单图安全上限
    --output-size 1024 \                        # 最终方图尺寸
    --resume \                                  # 跳过已完成
    --dry-run \                                 # 只检测不抠图
    --redetect                                  # 忽略缓存，重新检测
```

### 抠图策略

| `--matting` | 行为 |
|-------------|------|
| `auto`（默认） | 先 rembg；alpha 覆盖率 < 5% 时自动切到 nano-banana 品红底 + 色键 |
| `rembg`        | 始终走 rembg，不做兜底 |
| `magenta`      | 始终走 nano-banana 品红底 + numpy 色键（适合复杂边缘/发光特效） |

## 输出布局

```
output/
├── _run.jsonl                        # 每行一个图标的处理记录（用于 resume）
└── <screenshot_stem>/
    ├── _detection.json               # 检测原始 JSON
    ├── _overlay.png                  # 带 bbox + 标签的调试图
    ├── talent_node_01.png            # 1024×1024 RGBA
    ├── talent_node_02.png
    └── ui_frame_01.png
```

`_run.jsonl` 每条记录形如：

```json
{"ts": 1715491823.5, "screenshot": "foo.png", "stage": "extract",
 "status": "ok", "key": "foo.png|talent_node|245_310_385_450",
 "label": "talent_node", "idx": 1, "bbox": [245, 310, 385, 450],
 "matte": "rembg", "model": "gemini-3.1-flash-image-preview",
 "latency_ms": 4231, "out": "foo/talent_node_01.png"}
```

`--resume` 用 `screenshot|label|bbox_hash` 作为 key 跳过已完成项。

**检测缓存**：`_detection.json` 存在时，下次运行自动跳过检测步骤，直接复用结果（省去 API 调用）。若对 `_overlay.png` 中的检测框不满意，加 `--redetect` 强制重新检测；旧的 `_detection.json` 和 `_overlay.png` 会自动重命名为带时间戳的备份（如 `_detection_20260512_153000.json`），不会丢失。

## 成本估算（单张截图，约 20 个图标）

| 步骤 | 模型 | 单价 | 小计 |
|------|------|------|------|
| 检测 (1 次) | `gemini-3.1-pro-preview` | ~$0.04/图 | ~$0.04 |
| 抽图 (20 次) | `gemini-3.1-flash-image-preview` | $0.067/图 (1K) | ~$1.34 |
| 本地抠图 | rembg U2Net (CPU) | $0 | $0 |
| **合计** | | | **≈ $1.38** |

100 张约 $138。降本选项：
- `--detect-model gemini-3-flash`（检测改 Flash，省 ~$0.035/张）
- `--extract-model gemini-2.5-flash-image`（抠图改 2.5 Flash，每张省 ~40%）

## 错误处理

| 失败 | 处理 |
|------|------|
| Vertex 429/5xx | tenacity 指数退避 + jitter，最多 5 次 |
| 检测 JSON 解析失败 | 重试一次；仍失败则跳过该截图并日志 |
| nano-banana 安全过滤 | 记录失败状态，跳过该图标 |
| rembg alpha 覆盖率 < 5% | `auto` 模式自动切 magenta 色键 |
| bbox 越界 | 解析时 clamp 到图像边界 |

## 已知风险

1. **抠图边缘质量**：rembg U2Net 训练数据是自然图像，对游戏发光/粒子边缘可能有光晕。备选：换 `birefnet-general-lite`、用 `--matting magenta` 走色键
2. **`image_config` SDK 字段**：`google-genai` 预览版字段命名可能微调，[extract.py](src/picut/extract.py) 已用 `getattr` 探测自动降级
3. **检测召回率**：密集天赋树可能漏检小图标。先用 `detect` 子命令在 1-2 张上验证再批量
4. **中文文字误识别**：prompt 已显式排除"plain text labels"，仍可能假阳性，靠 `_overlay.png` 人工 QC

## 文件清单

```
pic_cut/
├── README.md
├── requirements.txt
├── .gitignore
├── .env.example
├── input/                  # 用户放截图
├── output/                 # 提取结果
└── src/picut/
    ├── __init__.py
    ├── cli.py
    ├── client.py
    ├── config.py
    ├── crop.py
    ├── detect.py
    ├── extract.py
    ├── log.py
    ├── matte.py
    ├── overlay.py
    ├── pipeline.py
    └── retry.py
```

## TODO / 后续可优化

- [ ] 加 `pyproject.toml`，`pip install -e .` 后直接 `picut` 命令调用，省掉 `PYTHONPATH=src`
- [ ] `--concurrency` 实际启用并发抠图（目前是顺序处理）
- [ ] 加 `--matting model=birefnet-general-lite` 选项暴露 rembg 模型切换
- [ ] 单元测试覆盖 detect 解析、bbox 反归一化、色键算法
