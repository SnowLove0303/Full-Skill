---
name: bilibili-all-in-one
description: B站综合工具箱 — 三大功能合一：AI早报（UP主视频→Whisper转录→Obsidian笔记）、热门日报（热门视频→AI总结→邮件推送）、关键词搜索（多UP主→批量下载→转录存档）。触发词：B站早报/AI日报/热门监控/邮件推送/bilibili搜索/bilibili监控/bilibili视频
triggers:
  - B站早报
  - AI早报
  - bilibili日报
  - B站热门
  - bilibili监控
  - bilibili搜索
  - bilibili视频
  - 热门视频邮件
links:
  - [[video-news-workflow]]
  - [[bilibili-opencli]]
---

# Bilibili All-in-One

> 三大功能合一：B站早报生成 / 热门日报邮件推送 / 关键词搜索下载
> 本 Skill = bilibili-news + bilibili-opencli + bilibili-monitor 整合版
> **所有脚本已打包在本 skill 目录的 `scripts/` 子目录下，完全自包含。**

---

## 快速安装和验证

优先使用打包脚本，默认把依赖、工具、缓存和下载目录分别放到 `E:\MorenAnzhuangLujing\Huangjingdajian` 下的独立文件夹：

```powershell
# 在 skill 根目录运行
.\scripts\setup.ps1 -RunSmokeTest

# 只检查环境
.\scripts\check_env.ps1

# 只跑 smoke test
.\scripts\smoke_test.ps1
```

安装脚本会创建：

- Python venv: `E:\MorenAnzhuangLujing\Huangjingdajian\python-venvs\bilibili-all-in-one`
- pip cache: `E:\MorenAnzhuangLujing\Huangjingdajian\tool-caches\pip\bilibili-all-in-one`
- Hugging Face / Whisper cache: `E:\MorenAnzhuangLujing\Huangjingdajian\tool-caches\huggingface\bilibili-all-in-one`
- OpenCLI: `E:\MorenAnzhuangLujing\Huangjingdajian\node-tools\opencli`
- Bilibili output: `E:\MorenAnzhuangLujing\Huangjingdajian\downloads\bilibili`
- Local env file: `.env.generated.ps1`

可选参数：

| 参数 | 作用 |
|------|------|
| `-InstallRoot <path>` | 更换工具安装根目录。 |
| `-SkipPythonDeps` | 不安装 Python venv 和 pip 依赖。 |
| `-SkipOpencli` | 不安装 OpenCLI。 |
| `-PersistUserEnv` | 把关键环境变量写入 Windows 用户环境变量。 |
| `-RunSmokeTest` | 安装后直接运行 smoke test。 |

---

## 站内搜索定位指定视频

当用户要求“必须找到某一期视频”时，优先使用 `--find-video`，它会先走 B 站站内搜索，再用作者、日期、标题片段和必含关键词过滤排序。`--bvid` 只适合已经知道 BV 后直接处理，不等同于站内搜索。

示例：从 B 站站内搜索定位橘鸦Juya 2026-05-03 这一期 AI 早报：

```powershell
$Skill = "F:\AIAPP\Codex\.codex\skills\bilibili-all-in-one-2026-04-18-v2"
$Py = "E:\MorenAnzhuangLujing\Huangjingdajian\python-venvs\bilibili-all-in-one\Scripts\python.exe"
$Run = "$Skill\scripts\bilibili-opencli\scripts\run.py"

& $Py $Run `
  --find-video "OpenAI OpenClaw AI早报 2026-05-03" `
  --author "橘鸦Juya" `
  --date 2026-05-03 `
  --must OpenClaw `
  --limit 10 `
  --strict-find `
  --dry-run
```

预期命中：`BV1ro9dBFEEB`，标题为 `OpenAI 宣布 ChatGPT 账户可登录 OpenClaw 复用订阅；猎豹移动AI产品被指抄袭开源项目【AI 早报 2026-05-03】`。

可用过滤参数：

| 参数 | 作用 |
|------|------|
| `--find-video <query>` | 使用 B 站站内搜索定位指定视频。 |
| `--author <name>` | 限定 UP 主/作者名称。 |
| `--title <text>` | 限定标题片段。 |
| `--must <term>` | 要求标题/作者/BV/日期中必须包含该词，可重复。 |
| `--strict-find` | 找不到匹配视频时返回非零退出码，适合自动化。 |
| `--keep-cache` | 写完笔记后保留音频、视频和转录缓存；默认会清理过程缓存并释放 ASR 模型内存。 |

---

## 目录结构

```
bilibili-all-in-one/
├── SKILL.md              # 本文档
├── quick-ref.md           # 快速参考
├── scripts/
│   ├── bilibili-news/           # 功能一：B站早报（Whisper转录→Obsidian）
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── run_ai_news.bat      # Windows 快速启动
│   │   ├── bilibili_news/
│   │   │   ├── __init__.py
│   │   │   └── __main__.py
│   │   └── skill.json
│   ├── bilibili-opencli/        # 功能三：关键词搜索下载
│   │   ├── SKILL.md
│   │   ├── opencli_bilibili.py
│   │   ├── skill.json
│   │   └── scripts/
│   │       ├── run.py           # 主入口
│   │       ├── search.py
│   │       ├── download.py
│   │       ├── transcribe.py
│   │       ├── formatter.py
│   │       └── bilibili_utils.py
│   ├── bilibili-hot-monitor/    # 功能二：热门日报+邮件推送
│   │   ├── SKILL.md
│   │   ├── README.md
│   │   ├── bilibili_api.py
│   │   ├── bilibili_subtitle.py
│   │   ├── generate_report.py   # 主入口
│   │   ├── send_email.py
│   │   ├── requirements.txt
│   │   ├── bilibili-monitor.example.json
│   │   └── _meta.json
│   └── video-news-workflow/     # 跨 skill 共享工具
│       ├── opencli_bilibili.py
│       └── run_bilibili_monitor.py
```

---

## 环境依赖

| 依赖 | 说明 |
|------|------|
| Python | `python3` 3.10+ |
| opencli | 可选。设置 `OPENCLI_CMD` 或放入 `PATH`；不可用时会使用公开 API 兜底搜索/列 UP 投稿。 |
| opencli 禁用开关 | 设置 `BILIBILI_DISABLE_OPENCLI=1` 时跳过 opencli，直接走公开 API。 |
| yt-dlp | `pip install yt-dlp`，用于下载音视频。 |
| ffmpeg | 放入 `PATH`，或按本机工具目录配置。 |
| Whisper | 可通过 `WHISPER_MODEL_SMALL` / `WHISPER_MODEL_MEDIUM` 指向本地 faster-whisper 模型。 |
| Whisper 自动模型 | 没有本地模型时使用 `WHISPER_MODEL_NAME`，默认 `tiny`，缓存到 `WHISPER_DOWNLOAD_ROOT`。 |
| FunASR | 可通过 `FUNASR_VENV` 指向本地虚拟环境。 |
| 临时目录 | 可通过 `BILIBILI_OUTPUT_DIR` 覆盖；默认 `~/bilibili-ai-news`。 |
| Obsidian Vault | 可通过 `BILIBILI_VAULT_DIR` 覆盖；默认 `~/Documents/Obsidian Vault/实时快报`。 |

### 本版优化

- 移除旧版文档和脚本里对固定 Windows 用户目录的依赖。
- `opencli` 优先读取 `OPENCLI_CMD`，其次从 `PATH` 自动发现。
- 当 `opencli` 不存在或不返回 JSON 时，搜索会自动走 Bilibili 公开搜索接口兜底。
- `--uid` UP 主视频列表补充 WBI 签名公开接口兜底；若 Bilibili 风控拦截，建议配置 `opencli`。
- 输出目录、Vault、Whisper/FunASR 路径均可用环境变量覆盖。
- `setup.ps1` 提供一键安装 Python 依赖、OpenCLI、缓存目录和 smoke test。
- Windows PowerShell 传中文搜索词前可先执行 `chcp 65001`；也可用 UID/BV 避免命令行编码问题。

---

## 三大功能

### 功能一：B站早报（UP主视频 → Whisper转录 → Obsidian笔记）

```
UP主视频获取 → 音频下载 → Whisper转录 → 生成结构化笔记 → 写入Obsidian
```

**自包含脚本路径：**
```
<skill-root>/scripts/bilibili-opencli/scripts/run.py
```

```powershell
# 设置为你的 skill 安装路径
$Skill = "F:\AIAPP\Codex\.codex\skills\bilibili-all-in-one-2026-04-18-v2"

# 方式A：单UP主，当日视频
python "$Skill\scripts\bilibili-opencli\scripts\run.py" `
    --uid 285286947 --limit 5 --date 2026-04-18

# 方式B：多UP主批量
python "$Skill\scripts\bilibili-opencli\scripts\run.py" `
    --uid 285286947 --limit 3
python "$Skill\scripts\bilibili-opencli\scripts\run.py" `
    --uid 1638385490 --limit 3

# 方式C：关键词搜索
python "$Skill\scripts\bilibili-opencli\scripts\run.py" `
    --search "AI 大模型" --limit 10

# 方式D：dry-run（只打印，不下载）
python "$Skill\scripts\bilibili-opencli\scripts\run.py" `
    --uid 285286947 --limit 3 --dry-run
```

**run.py 参数说明：**

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--uid` | UP主 UID（二选一） | - |
| `--search` | 关键词搜索（二选一） | - |
| `--limit` | 获取视频数量 | 5 |
| `--date` | 日期过滤 YYYY-MM-DD | 当日 |
| `--output` | 下载目录 | `BILIBILI_OUTPUT_DIR` 或 `~/bilibili-ai-news` |
| `--vault` | Obsidian 笔记目录 | `BILIBILI_VAULT_DIR` 或 `~/Documents/Obsidian Vault/实时快报` |
| `--parallel` | 并行下载/转录数 | 1 |
| `--dry-run` | 只打印，不下载/转录 | - |
| `--skip-transcribe` | 跳过转录 | - |
| `--skip-download` | 跳过下载 | - |
| `--force-transcribe` | 强制重转（覆盖已有txt） | - |

**转录引擎策略：**
1. 优先：`faster-whisper-small` 本地模型（`F:\AI\whisper_models\faster-whisper-small`）
2. 兜底：FunASR SenseVoice（`F:\skill\funasr-skill\.venv`）

**输出格式：**
```
{vault}/{date} AI早报-{UP名}.md
```

---

### 功能二：热门日报（热门视频 → AI总结 → 邮件推送）

> 需要：Chrome 已登录B站Cookies + OpenRouter API Key + Gmail发件账号

**首次配置（分步询问）：**

**Step 1：获取B站Cookies**
```
登录B站 → F12 → Network → 刷新页面 → 点击 www.bilibili.com 请求
→ Request Headers → 复制 Cookie 字段完整值
```

**Step 2：选择AI模型**
```
1 = Gemini（推荐，便宜快速）
2 = Claude（高质量）
3 = GPT
4 = DeepSeek（性价比）
```

**Step 3：获取OpenRouter API Key**
```
https://openrouter.ai/keys
```

**Step 4：Gmail发件配置**
```
发件邮箱 + Gmail应用密码（16位）
获取应用密码：https://myaccount.google.com/apppasswords
```

**Step 5：配置收件人**
```
收件邮箱（多个用逗号分隔）
```

**配置文件路径：** `F:\openclaw1\.openclaw\workspace\skills\bilibili-hot-monitor\bilibili-monitor.json`

**执行热门日报：**

```bash
# 生成报告
python3 F:\openclaw1\.openclaw\workspace\skills\bilibili-hot-monitor\generate_report.py \
    --config F:\openclaw1\.openclaw\workspace\skills\bilibili-hot-monitor\bilibili-monitor.json \
    --output /tmp/bilibili_report.md

# 发送邮件
python3 F:\openclaw1\.openclaw\workspace\skills\bilibili-hot-monitor\send_email.py \
    --config F:\openclaw1\.openclaw\workspace\skills\bilibili-hot-monitor\bilibili-monitor.json \
    --body-file /tmp/bilibili_report.md --html
```

**执行时间：** 10-15分钟（包含字幕提取+AI总结+AI点评），超时设置 900秒以上。

**OpenRouter 模型映射：**

| 选择 | model |
|------|-------|
| Gemini | `google/gemini-3-flash-preview` |
| Claude | `anthropic/claude-sonnet-4.5` |
| GPT | `openai/gpt-5.2-chat` |
| DeepSeek | `deepseek/deepseek-chat-v3-0324` |

> ⚠️ AI总结基于字幕生成，无字幕视频无法总结。

---

### 功能三：关键词搜索（多UP主 → 批量下载 → 转录存档）

```python
import sys
sys.path.insert(0, '~/.hermes/skills/bilibili-all-in-one/scripts/bilibili-opencli/scripts')
from bilibili_utils import search_videos, get_user_videos

# 关键词搜索
results = search_videos('AI 早报', limit=10)

# UP主视频列表
videos = get_user_videos('285286947', limit=20)
# 返回: bvid, title, author, score, url, plays, date, source
```

```python
from download import download_batch

results = download_batch(videos, output_dir='F:/工作区间/ai_news_temp', parallel=2, skip_existing=True)
# 返回: [{bvid, title, status, files: {.mp4, .m4a, .jpg}}]
```

---

## 核心脚本入口（自包含路径）

| 脚本 | 功能 | 调用方式 |
|------|------|---------|
| `scripts/bilibili-opencli/scripts/run.py` | 早报CLI入口 | `python run.py --uid X --limit 5` |
| `scripts/bilibili-opencli/scripts/bilibili_utils.py` | 搜索/列表 | import 调用 |
| `scripts/bilibili-opencli/scripts/download.py` | 批量下载 | import 调用 |
| `scripts/bilibili-opencli/scripts/transcribe.py` | Whisper转录 | import 调用 |
| `scripts/bilibili-opencli/scripts/formatter.py` | Obsidian笔记 | import 调用 |
| `scripts/bilibili-hot-monitor/generate_report.py` | 热门日报生成 | python 直接调用 |
| `scripts/bilibili-hot-monitor/send_email.py` | 邮件推送 | python 直接调用 |
| `scripts/bilibili-hot-monitor/bilibili_api.py` | B站API/字幕 | import 调用 |

---

## 已知坑点

1. **PowerShell中文乱码**：控制台中文显示乱码是PowerShell问题，不影响文件写入，Obsidian笔记正常。
2. **Whisper medium模型**：需要网络下载，当前环境只有small可用。如需medium，设置 `ASR_ENGINE=funasr` 强制FunASR。
3. **无字幕视频**：热门日报AI总结依赖字幕，无字幕视频跳过总结。
4. **Cookies时效**：B站Cookies会过期，热门日报失效时需重新获取。
5. **执行超时**：热门日报完整执行10-15分钟，命令超时设900秒以上。

---

## 快速选择指南

| 需求 | 用哪个功能 |
|------|---------|
| 想把某个UP主最新视频做成Obsidian笔记 | 功能一：B站早报 |
| 想做B站热门视频日报发邮件 | 功能二：热门日报 |
| 想搜某个关键词相关视频并下载 | 功能三：关键词搜索 |
| 想批量处理多个UP主的视频 | 功能一 + `--parallel 2` |
