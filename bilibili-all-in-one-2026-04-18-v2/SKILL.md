---
name: bilibili-all-in-one
description: B站唯一入口技能，整合原 bilibili-news、bilibili-opencli、bilibili-monitor 及其脚本模块；支持 AI早报、站内搜索、视频下载转录、Obsidian笔记、热门日报、邮件推送、账号登录态复用、视频证据包、弹幕分析、关键帧、订阅监控、内容雷达、直播快照、直播弹幕监听、合集计划、转录修复和轻量工具服务。触发词：B站早报/AI日报/热门监控/邮件推送/bilibili搜索/bilibili监控/bilibili视频/B站Cookie/证据包/弹幕/直播/UP主订阅
triggers:
  - B站早报
  - AI早报
  - bilibili日报
  - B站热门
  - 热门视频
  - 视频日报
  - bilibili监控
  - bilibili搜索
  - bilibili视频
  - bilibili-opencli
  - bilibili-monitor
  - 热门视频邮件
  - 视频证据包
  - B站弹幕
  - UP主订阅
  - B站内容雷达
  - B站直播
  - B站Cookie
  - B站账号登录
  - 转录修复
links:
  - [[quick-ref]]
---

# Bilibili All-in-One

> 多功能合一：B站早报生成 / 热门日报邮件推送 / 关键词搜索下载 / 账号登录态复用 / 视频证据包 / 弹幕分析 / 订阅监控 / 内容雷达 / 直播快照与实时弹幕
> 本 Skill 是 bilibili-news + bilibili-opencli + bilibili-monitor + video-news-workflow 的唯一入口整合版。
> **所有脚本已打包在本 skill 目录的 `scripts/` 子目录下，完全自包含。**

## 整合状态

- Codex 只应把本文件识别为 Bilibili 技能入口。
- 原 `bilibili-opencli` 和 `bilibili-monitor` 子技能已降级为脚本模块文档：`scripts/bilibili-opencli/MODULE.md`、`scripts/bilibili-hot-monitor/MODULE.md`。
- 原 `bilibili-news`、`bilibili-opencli`、`bilibili-hot-monitor`、`video-news-workflow` 脚本全部保留在 `scripts/` 下，由本技能统一调度。
- 新增扩展模块 `scripts/bilibili-expander`，用于账号 Cookie 登录态复用、证据包、弹幕、字幕、下载后端探测、内容雷达、UP 主订阅、直播快照、直播弹幕监听、合集计划、转录修复和轻量工具服务。
- 遇到 B站、Bilibili、视频日报、AI早报、UP主视频、转录、Obsidian笔记、热门视频邮件、弹幕、证据包、直播、订阅监控等需求时，先读本文件，再按“快速选择指南”选内部模块。

---

## 执行原则

1. 先定位视频，再处理内容。需要找“某一天/某一期/某个 UP 主”的视频时，优先用 `--find-video` 或 `--uid` dry-run 验证标题、作者、日期和 BV；不要把搜索页、推荐页或播放页 HTML 当成转录来源。
2. 需要账号态时，优先复用 `chrome-login` / `cookie-from-chrome` 保存的本地 Cookie state；不要让用户手动复制明文 Cookie，除非自动桥接失败。
3. 生成日报、Notion 页面、Open Notebook 内容前，必须确认来源文本是字幕、ASR 转录或人工整理后的正文；如果只有 URL、页面导航、推荐视频、报错占位或元数据，应判定为未完成。
4. 自动化产物验收至少检查：标题不是 `Processing...`，正文不是乱码，来源不是 `URL Source:` 页面抓取，转录长度与视频时长大致匹配，Open Notebook 入库时 `embedded_chunks` 大于 0。
5. 涉及定时任务或外部 agent 时，Codex 负责派发和验收；被调 agent 必须回传视频清单、BV、输出路径、失败原因和可复核证据。

---

## 快速选择指南

| 需求 | 首选入口 | 验收点 |
|------|---------|--------|
| 找指定日期/标题的视频 | `run.py --find-video ... --strict-find --dry-run` | 命中作者、标题关键词、日期、BV |
| 处理已知 BV | `run.py --bvid BVxxxx` | 成功下载/转录并生成笔记 |
| UP 主日报/早报 | `run.py --uid <uid> --limit N` | 输出 Obsidian 笔记，正文含转录摘要 |
| 热门日报邮件 | `bilibili-hot-monitor/generate_report.py` + `send_email.py` | 报告生成、邮件发送成功 |
| 账号登录态 | `bilibili-expander/cli.py chrome-login` | `cookie-status` 返回可用登录态 |
| 视频证据包 | `bilibili-expander/cli.py evidence-pack` | 元数据、字幕、弹幕、关键帧或 smoke report 存在 |
| 弹幕/字幕单独导出 | `danmaku` / `subtitle` | JSON 文件存在且条目数合理 |
| 内容雷达 | `radar` | 排行榜和关键词结果已写入 Markdown |
| UP 主订阅监控 | `subscribe-check` | state 更新，报告列出新增/无新增 |
| 直播快照/弹幕 | `live-snapshot` / `live-danmaku` | JSON 或 JSONL 输出可解析 |
| 转录术语修复 | `polish-transcript` | 输出文件替换术语且保留正文 |

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

示例：从 B 站站内搜索定位橘鸦Juya 2026-05-03 这一期 AI 早报。站内搜索结果会随 B 站排序和风控变化，自动化校验不要依赖固定 BV：

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

历史命中过：`BV1ro9dBFEEB`，标题为 `OpenAI 宣布 ChatGPT 账户可登录 OpenClaw 复用订阅；猎豹移动AI产品被指抄袭开源项目【AI 早报 2026-05-03】`。

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
│   │   ├── MODULE.md            # 旧子技能说明，现为模块文档
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
│   │   ├── MODULE.md            # 旧子技能说明，现为模块文档
│   │   ├── README.md
│   │   ├── bilibili_api.py
│   │   ├── bilibili_subtitle.py
│   │   ├── generate_report.py   # 主入口
│   │   ├── send_email.py
│   │   ├── requirements.txt
│   │   ├── bilibili-monitor.example.json
│   │   └── _meta.json
│   ├── bilibili-expander/       # 扩展功能：证据包/弹幕/雷达/订阅/直播监听/工具服务
│   │   ├── MODULE.md
│   │   ├── cli.py              # 扩展统一入口
│   │   ├── core.py
│   │   ├── chrome_cookie.py    # Chrome DevTools 登录态/Cookie 桥接
│   │   ├── chrome_login.ps1    # Windows 扫码登录包装脚本
│   │   └── subscriptions.example.json
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
| `--parallel` | 并行下载/转录数 | 3 |
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

**Step 1：获取或复用 B站 Cookies**

优先用技能内置的 Chrome 登录态桥接，不再手动从 DevTools 复制 Cookie。它会启动一个可复用的 Chrome 用户目录，打开 B 站登录页，扫码登录后通过本地 DevTools 端口读取 `.bilibili.com` Cookie，保存到未跟踪的 `.runtime\bilibili-cookie-state.json`，并写入本地 `.env.generated.ps1`：

```powershell
$Skill = "F:\AIAPP\Codex\.codex\skills\bilibili-all-in-one-2026-04-18-v2"
$Py = "E:\MorenAnzhuangLujing\Huangjingdajian\python-venvs\bilibili-all-in-one\Scripts\python.exe"
$Expander = "$Skill\scripts\bilibili-expander\cli.py"

# 首次：打开 Chrome，扫码登录，等待并保存 Cookie
& $Py $Expander chrome-login --port 9222 --wait-login 180

# 后续：已有 Chrome 远程调试端口时，直接复用登录态
& $Py $Expander cookie-from-chrome --cdp-url http://127.0.0.1:9222 --wait-login 30

# 查看状态；输出只展示脱敏 Cookie
& $Py $Expander cookie-status
```

也可以直接运行 PowerShell 包装脚本：

```powershell
.\scripts\bilibili-expander\chrome_login.ps1 -Port 9222 -WaitSeconds 180
```

若你已经手动拿到 Cookie，也可设置 `BILIBILI_COOKIE`。脚本优先读取环境变量，其次读取 `.runtime\bilibili-cookie-state.json`。

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

**配置文件路径：** `<skill-root>\scripts\bilibili-hot-monitor\bilibili-monitor.json`

**执行热门日报：**

```powershell
$Skill = "F:\AIAPP\Codex\.codex\skills\bilibili-all-in-one-2026-04-18-v2"
$Monitor = "$Skill\scripts\bilibili-hot-monitor"

# 生成报告
python "$Monitor\generate_report.py" `
    --config "$Monitor\bilibili-monitor.json" `
    --output "$env:TEMP\bilibili_report.md"

# 发送邮件
python "$Monitor\send_email.py" `
    --config "$Monitor\bilibili-monitor.json" `
    --body-file "$env:TEMP\bilibili_report.md" --html
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
sys.path.insert(0, r'F:\AIAPP\Codex\.codex\skills\bilibili-all-in-one-2026-04-18-v2\scripts\bilibili-opencli\scripts')
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

## 扩展功能：证据包 / 弹幕 / 雷达 / 订阅 / 直播

扩展模块统一入口：

```powershell
$Skill = "F:\AIAPP\Codex\.codex\skills\bilibili-all-in-one-2026-04-18-v2"
$Expander = "$Skill\scripts\bilibili-expander\cli.py"
python $Expander --help
```

### 账号 Cookie / 登录态复用

需要登录态的场景包括部分高清视频下载、受风控接口、热门日报和需要账号权限的视频内容。扩展模块提供三种入口：

```powershell
# 启动可复用 Chrome Profile，扫码登录后自动保存 Cookie
python $Expander chrome-login --port 9222 --wait-login 180

# 连接已有 Chrome DevTools 端口，读取当前登录态
python $Expander cookie-from-chrome --cdp-url http://127.0.0.1:9222 --wait-login 30

# 查看是否有可用 Cookie；默认会调用 B 站 nav API 验证 isLogin
python $Expander cookie-status
```

默认保存位置：

- Cookie state: `.runtime\bilibili-cookie-state.json`
- PowerShell env: `.env.generated.ps1`
- Chrome profile: `.runtime\chrome-profile`

这些路径已按仓库规则忽略，不应提交。`http_json`、`http_bytes`、`download`、`evidence-pack --download` 会自动优先读取 `BILIBILI_COOKIE`，否则读取 Cookie state；下载尝试报告中的 Cookie 会被脱敏。

### 视频证据包

用于把单个视频整理成可复核资料包，适合事实核查、教程复盘、剪辑前分析和研究笔记。

产物：

- `metadata.json`：视频元数据、UP 主、播放/点赞/收藏等统计
- `subtitles.json`：官方字幕
- `danmaku.json`：弹幕 JSON
- `danmaku.ass`：可挂载的 ASS 弹幕字幕
- `frames/*.jpg`：关键帧截图，有本地媒体或启用下载时生成
- `sectioned.md`：汇总笔记
- `smoke-report.json`：本次采集状态

```powershell
# 只抓元数据、字幕、弹幕，不下载媒体
python $Expander evidence-pack --bvid BVxxxx --output "$env:TEMP\bilibili-evidence"

# 下载媒体并抽关键帧
python $Expander evidence-pack `
  --bvid BVxxxx `
  --download `
  --backend auto `
  --every-seconds 30 `
  --frame-limit 24 `
  --output "$env:TEMP\bilibili-evidence"
```

### 弹幕与字幕

```powershell
# 弹幕 JSON
python $Expander danmaku --bvid BVxxxx --output "$env:TEMP\danmaku.json"

# 官方字幕 JSON
python $Expander subtitle --bvid BVxxxx --lang zh-CN --output "$env:TEMP\subtitles.json"
```

弹幕可以进一步用于高频词、热度时间轴、情绪倾向和视频片段复盘。证据包会自动生成基础高频词列表。

### 下载后端适配

扩展模块会探测并按需使用：

- `BBDown`
- `yutto`
- `yt-dlp`
- `python -m yt_dlp`

```powershell
python $Expander backends
python $Expander download --bvid BVxxxx --backend auto --output "$env:TEMP\bilibili-downloads"
```

当一个后端不可用或失败时，可切换到另一个后端。涉及番剧、合集、课程时，优先考虑 BBDown 或 yutto；普通单视频可用 yt-dlp。若已有登录态，下载命令会自动把 Cookie 传给 BBDown、yutto 或 yt-dlp，并在日志中脱敏。

### 内容雷达

用于生成排行榜 + 关键词搜索报告，适合做分区趋势、AI 区日报、选题监控。

```powershell
python $Expander radar `
  --keyword "AI 大模型" `
  --keyword "OpenAI" `
  --limit 10 `
  --output "$env:TEMP\bilibili-radar.md"
```

### UP 主订阅监控

用于检查一组 UP 主是否有新投稿，维护本地 state，输出增量报告。

配置格式：

```json
{
  "limit": 10,
  "users": [
    {"uid": "285286947", "name": "示例UP主"}
  ]
}
```

命令：

```powershell
python $Expander subscribe-check `
  --config "$Skill\scripts\bilibili-expander\subscriptions.example.json" `
  --state "$env:TEMP\bilibili-sub-state.json" `
  --output "$env:TEMP\bilibili-sub-report.md"
```

### 直播快照与弹幕监听

用于获取直播间当前标题、状态、分区、在线人数，也可以直接连接 B 站直播弹幕 WebSocket，把实时弹幕保存成 JSONL 和 Markdown 摘要。

```powershell
python $Expander live-snapshot --room-id 6 --output "$env:TEMP\bilibili-live.json"

python $Expander live-danmaku `
  --room-id 6 `
  --seconds 60 `
  --max-messages 200 `
  --output "$env:TEMP\bilibili-live-danmaku.jsonl"
```

`live-danmaku` 不依赖第三方 Python 包，使用标准库完成 WebSocket 握手、心跳、B 站包解析和 zlib 解压。默认只保存弹幕；如需礼物、进场、热度等事件，加 `--include-events`。

### 合集 / 课程 / 批量计划

用于把多个 BV/URL 整理成一个处理计划，后续可接下载、转录、证据包或笔记生成。

```powershell
python $Expander collection-plan BVxxxx BVyyyy --output "$env:TEMP\bilibili-collection.md"
```

### 转录质量修复

用于统一空白、清理文本，并按术语表修正常见 ASR 错误。

术语表示例：

```json
{
  "欧喷AI": "OpenAI",
  "克劳德": "Claude"
}
```

命令：

```powershell
python $Expander polish-transcript `
  --input transcript.txt `
  --glossary glossary.json `
  --output transcript.polished.txt
```

### 轻量工具服务

`mcp-stdio` 提供 JSON-lines 本地工具服务，便于 Agent 或 chromedify 风格浏览器自动化把 B 站能力当工具调用。

```powershell
python $Expander mcp-stdio
```

请求格式：

```json
{"id":"1","tool":"bilibili.video_info","params":{"bvid":"BVxxxx"}}
```

当前工具：

- `bilibili.video_info`
- `bilibili.subtitles`
- `bilibili.danmaku`
- `bilibili.live_snapshot`
- `bilibili.backends`

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
| `scripts/bilibili-expander/cli.py` | 证据包/弹幕/雷达/订阅/直播监听/转录修复 | `python cli.py <command>` |
| `scripts/bilibili-expander/chrome_cookie.py` | Chrome登录态/Cookie桥接 | `python cli.py chrome-login` |
| `scripts/bilibili-expander/chrome_login.ps1` | Windows扫码登录包装脚本 | `.\scripts\bilibili-expander\chrome_login.ps1` |

---

## 已知坑点

1. **PowerShell中文乱码**：控制台中文显示乱码是PowerShell问题，不影响文件写入，Obsidian笔记正常。
2. **Whisper medium模型**：需要网络下载，当前环境只有small可用。如需medium，设置 `ASR_ENGINE=funasr` 强制FunASR。
3. **无字幕视频**：热门日报AI总结依赖字幕，无字幕视频跳过总结。
4. **Cookies时效**：B站Cookies会过期，热门日报或下载失败时先跑 `cookie-status`；失效后用 `chrome-login` 重新扫码。
5. **执行超时**：热门日报完整执行10-15分钟，命令超时设900秒以上。
6. **凭证安全**：`.runtime\bilibili-cookie-state.json` 和 `.env.generated.ps1` 含明文 Cookie，仅保存在本机且已被 `.gitignore` 排除；不要贴到聊天或提交仓库。

---

## 维护约定

- 新增 Bilibili 相关能力时，优先增加到本技能的 `scripts/` 子模块，并在本文件登记入口。
- 不要在子目录新增 `SKILL.md`；子模块说明使用 `MODULE.md` 或 `README.md`，避免重新暴露多个 Codex 技能。
- 旧模块元数据如 `skill.json`、`_meta.json` 仅作为脚本兼容信息保留，不代表独立 Codex 技能入口。
- `scripts/bilibili-expander` 是扩展能力的默认承载模块；若新增功能只是 B 站资料采集、分析、证据化、订阅监控或 Agent 工具化，优先放入该模块。
