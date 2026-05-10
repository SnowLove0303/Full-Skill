# Bilibili OpenCLI 模块

> 本文件是 `bilibili-all-in-one` 的内部模块文档，不再是独立 Codex Skill。
> 唯一技能入口：`../../SKILL.md`。

**功能**：用 `opencli bilibili` 命令搜索 → 下载 → Whisper/FunASR 转录 → 生成 Obsidian 笔记  
**支持**：批量处理、多UP主、日期过滤

---

## 环境依赖

- **opencli**: `C:\Users\chenz\AppData\Roaming\npm\opencli.cmd`（已安装）
- **yt-dlp**: opencli 内置（视频下载）
- **Whisper**: `F:\AI\whisper_models\faster-whisper-small`（本地模型，英文强、中文弱）
- **FunASR**: `F:\skill\funasr-skill\.venv`（SenseVoice，**中文强、英文专有名词弱**，需要 WinGet ffmpeg）
- **FFmpeg**: `C:\Users\chenz\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin`（winget install Gyan.FFmpeg 安装）
- **转录引擎默认**: `auto`（Whisper 优先，失败自动切换 FunASR）
- **输出目录**: `F:\工作区间\ai_news_temp`
- **Obsidian**: `C:\Users\chenz\Documents\Obsidian Vault\实时快报`

---

## 命令行用法

### 搜索 + 下载 + 转录（单UP主，当日视频）

```powershell
python scripts/run.py --uid 285286947 --limit 5 --date 2026-04-09
```

### 关键词搜索（所有UP主）

```powershell
python scripts/run.py --search "AI 早报" --limit 5
```

### 只搜索，不下载/转录

```powershell
python scripts/run.py --uid 285286947 --limit 5 --date 2026-04-09 --dry-run
```

### 跳过转录（只要下载）

```powershell
python scripts/run.py --uid 285286947 --limit 3 --skip-transcribe
```

### 强制重转（覆盖已有txt）

```powershell
python scripts/run.py --uid 285286947 --limit 3 --force-transcribe
```

### 批量多UP（示例）

```powershell
python scripts/run.py --uid 285286947 --limit 3 --date 2026-04-09
python scripts/run.py --uid 1638385490 --limit 3 --date 2026-04-09
```

---

## 核心模块

### bilibili_utils.py — OpenCLI 封装

```python
from bilibili_utils import search_videos, get_user_videos

# 关键词搜索
results = search_videos('AI 大模型', limit=10)

# UP 主视频列表
videos = get_user_videos('285286947', limit=20)
```

返回字段: `bvid, title, author, score, url, plays, date, source`

### download.py — 批量下载

```python
from download import download_batch

results = download_batch(videos, output_dir, parallel=2, skip_existing=True)
# 返回: [{bvid, title, status, files: {.mp4, .m4a, .jpg}}]
```

### transcribe.py — 转录（Whisper 优先，FunASR 兜底）

```python
from transcribe import transcribe, transcribe_batch

# 单个
r = transcribe('BV11jDnBfErS', skip_existing=True)
print(r['text'], r['status'])

# 批量
results = transcribe_batch(bvid_list, parallel=2)
```

引擎策略:
1. Whisper small（本地模型 `F:\AI\whisper_models\faster-whisper-small`）
2. FunASR SenseVoice（`F:\skill\funasr-skill\.venv`，Whisper 失败时兜底）

### formatter.py — Obsidian 笔记生成

```python
from formatter import generate_daily_summary

summary = generate_daily_summary(videos, temp_dir=OUTPUT, vault_path=VAULT)
# 写入: {vault_path}/{date} AI早报-{UP名}.md
```

---

## run.py 主入口参数

| 参数 | 说明 |
|------|------|
| `--uid` | UP 主 UID |
| `--search` | 关键词搜索（与 --uid 二选一） |
| `--limit` | 获取视频数量（默认 5） |
| `--date` | 日期过滤（格式 YYYY-MM-DD） |
| `--output` | 下载目录（默认 `F:\工作区间\ai_news_temp`） |
| `--vault` | Obsidian 路径（默认 `C:\Users\chenz\Documents\Obsidian Vault\实时快报` |
| `--parallel` | 并行下载/转录数（默认 1） |
| `--dry-run` | 只打印，不下载/转录 |
| `--skip-transcribe` | 跳过转录 |
| `--skip-download` | 跳过下载 |
| `--force-transcribe` | 强制重转（覆盖已有 txt） |

---

## 已知问题 & 修复记录

### 🔧 2026-04-18 关键Bug修复

#### Bug 1: 转录文件名不匹配（transcribe.py 第126行）
- **问题**: `transcribe.py` 保存为 `{bvid}_transcript.txt`，但 `formatter.py` 查找 `transcript_{bvid}.txt`
- **症状**: formatter 生成空笔记（439字节），因为找不到转录文件
- **修复**: `transcribe.py` 第126行改为 `transcript_{bvid}.txt` 格式
- **验证**: 修复后笔记 2-3KB，有实质内容

#### Bug 2: B站音频 codec 错误（download.py）
- **问题**: B站 mp4 里的音频是 AAC，不是 OPUS。用 `libopus` 提取生成 0 字节 m4a
- **症状**: 转录被跳过（音频文件0字节），笔记为空
- **修复**: `download.py` 的 ffmpeg 命令改为 `-acodec copy`（不转码直接提取）
- **临时补救**: 手动用 `ffmpeg -acodec copy` 重新提取已有 mp4 的音频

#### Bug 3: WSL Python 无法解析 Windows 路径
- **问题**: `formatter.py` 在 WSL Python 下运行，Path('F:\...') 返回 exists=False
- **症状**: 笔记内容为空（找不到转录文件）
- **修复**: 所有 bilibili-opencli 调用必须通过 PowerShell 执行（不能用 WSL bash）

#### Bug 4: 日期过滤太严格（cron_bilibili.py）
- **问题**: `--date 2026-04-18` 只匹配当天发布的视频，差一天就全过滤掉
- **症状**: UP主4月17日发布视频，cron跑在4月18日，0个视频被处理
- **修复**: cron_bilibili.py 去掉 `--date` 参数，或用 `--days-back 3` 更灵活

#### Bug 5: FunASR 英文专有名词弱
- **症状**: "Google" → "谷歌"，"Anthropic" → 音译错误，"Claude" 识别差
- **现状**: FunASR SenseVoice 中文流利但英文弱；faster-whisper small 英文好但中文弱
- **建议**: 纯中文视频用 FunASR（auto），中英混杂视频考虑 faster-whisper medium

### 🔑 正确调用方式（必须用 PowerShell）

```powershell
# FFMPEG PATH 必须在 PowerShell 里设置（WSL bash 不生效）
$env:PATH = 'C:\Users\chenz\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin;' + $env:PATH

# 通过 PowerShell 调用 bilibili-opencli（不能用 WSL bash）
$Skill = "F:\AIAPP\Codex\.codex\skills\bilibili-all-in-one-2026-04-18-v2"
python "$Skill\scripts\bilibili-opencli\scripts\run.py" --uid 285286947 --limit 3
```

### FFmpeg 正确路径（winget 安装）
`C:\Users\chenz\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin`

### 其他已知问题

- **PowerShell 控制台编码**: 中文显示乱码是 PowerShell 问题，不影响文件写入。 Obsidian 文件正常显示。
- **Whisper 模型**: medium 模型需要网络下载，当前环境只有 small 可用。如需 medium，设置 `ASR_ENGINE=funasr` 强制使用 FunASR。
