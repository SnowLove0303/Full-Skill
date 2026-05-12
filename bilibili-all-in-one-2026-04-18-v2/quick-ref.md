# Bilibili All-in-One 快速参考

## 一键安装/检查

```powershell
# 默认安装到 E:\MorenAnzhuangLujing\Huangjingdajian 下的独立目录
.\scripts\setup.ps1 -RunSmokeTest

# 只检查环境
.\scripts\check_env.ps1

# 只跑 smoke test
.\scripts\smoke_test.ps1
```

## 常用命令

在 skill 根目录外执行时，先设置路径：

```powershell
$Skill = "F:\AIAPP\Codex\.codex\skills\bilibili-all-in-one-2026-04-18-v2"
$Py = "E:\MorenAnzhuangLujing\Huangjingdajian\python-venvs\bilibili-all-in-one\Scripts\python.exe"
$Run = "$Skill\scripts\bilibili-opencli\scripts\run.py"
$Expander = "$Skill\scripts\bilibili-expander\cli.py"
```

### 站内搜索定位指定视频

这是推荐给“必须找到指定视频”的模式。它会先走 B 站站内搜索，再用作者、日期、标题/关键词过滤并排序。

```powershell
& $Py $Run `
  --find-video "OpenAI OpenClaw AI早报 2026-05-03" `
  --author "橘鸦Juya" `
  --date 2026-05-03 `
  --must OpenClaw `
  --limit 10 `
  --strict-find `
  --dry-run
```

历史命中过：

```text
BV1ro9dBFEEB
橘鸦Juya
OpenAI 宣布 ChatGPT 账户可登录 OpenClaw 复用订阅；猎豹移动AI产品被指抄袭开源项目【AI 早报 2026-05-03】
```

### 普通关键词搜索

```powershell
& $Py $Run --search "橘鸦Juya" --limit 3 --dry-run
```

### UP 主投稿列表

```powershell
& $Py $Run --uid 285286947 --limit 3 --dry-run
```

### 直接指定 BV

```powershell
& $Py $Run --bvid BV1ro9dBFEEB --dry-run
```

### 视频证据包

```powershell
& $Py $Expander evidence-pack --bvid BVxxxx --output "$env:TEMP\bilibili-evidence"
```

下载媒体并抽关键帧：

```powershell
& $Py $Expander evidence-pack `
  --bvid BVxxxx `
  --download `
  --backend auto `
  --every-seconds 30 `
  --frame-limit 24
```

### 弹幕 / 字幕

```powershell
& $Py $Expander danmaku --bvid BVxxxx --output "$env:TEMP\danmaku.json"
& $Py $Expander subtitle --bvid BVxxxx --lang zh-CN --output "$env:TEMP\subtitles.json"
```

### 下载后端探测和切换

```powershell
& $Py $Expander backends
& $Py $Expander download --bvid BVxxxx --backend auto --output "$env:TEMP\bilibili-downloads"
```

### 账号登录态 / Cookie 复用

```powershell
# 首次扫码登录；默认复用 .runtime\chrome-profile
& $Py $Expander chrome-login --port 9222 --wait-login 180

# 已有 Chrome DevTools 端口时复用
& $Py $Expander cookie-from-chrome --cdp-url http://127.0.0.1:9222 --wait-login 30

# 只看脱敏状态
& $Py $Expander cookie-status
```

本地 Cookie 会保存到 `.runtime\bilibili-cookie-state.json`，并写入 `.env.generated.ps1` 方便后续命令自动读取；两个文件都不应提交。

### 内容雷达

```powershell
& $Py $Expander radar `
  --keyword "AI 大模型" `
  --keyword "OpenAI" `
  --limit 10 `
  --output "$env:TEMP\bilibili-radar.md"
```

### UP 主订阅监控

```powershell
& $Py $Expander subscribe-check `
  --config "$Skill\scripts\bilibili-expander\subscriptions.example.json" `
  --state "$env:TEMP\bilibili-sub-state.json" `
  --output "$env:TEMP\bilibili-sub-report.md"
```

### 直播快照 / 实时弹幕 / 合集计划 / 转录修复

```powershell
& $Py $Expander live-snapshot --room-id 6 --output "$env:TEMP\bilibili-live.json"
& $Py $Expander live-danmaku --room-id 6 --seconds 60 --max-messages 200 --output "$env:TEMP\bilibili-live-danmaku.jsonl"
& $Py $Expander collection-plan BVxxxx BVyyyy --output "$env:TEMP\bilibili-collection.md"
& $Py $Expander polish-transcript --input transcript.txt --glossary glossary.json
```

## 参数速查

| 需求 | 参数 |
|------|------|
| 站内搜索定位指定视频 | `--find-video "搜索词"` |
| 限定 UP 主/作者 | `--author "橘鸦Juya"` |
| 限定标题片段 | `--title "OpenAI 宣布 ChatGPT"` |
| 必须包含某个词 | `--must OpenClaw`，可重复 |
| 找不到时返回非零退出码 | `--strict-find` |
| 普通关键词搜索 | `--search "关键词"` |
| 指定 UP 主 UID | `--uid 285286947` |
| 直接指定 BV | `--bvid BVxxxx` |
| 限制数量 | `--limit 3` |
| 只列出不下载 | `--dry-run` |
| 跳过下载 | `--skip-download` |
| 跳过转录 | `--skip-transcribe` |
| 指定日期 | `--date YYYY-MM-DD` |
| 写完笔记后保留音频/转录缓存 | `--keep-cache` |

## 扩展命令速查

| 需求 | 命令 |
|------|------|
| 生成证据包 | `evidence-pack --bvid BVxxxx` |
| 下载并抽关键帧 | `evidence-pack --bvid BVxxxx --download --backend auto` |
| 导出弹幕 JSON | `danmaku --bvid BVxxxx` |
| 导出官方字幕 | `subtitle --bvid BVxxxx` |
| 探测下载后端 | `backends` |
| 用 BBDown/yutto/yt-dlp 下载 | `download --bvid BVxxxx --backend auto` |
| 扫码登录并保存 Cookie | `chrome-login --port 9222 --wait-login 180` |
| 从已有 Chrome 端口抽取 Cookie | `cookie-from-chrome --cdp-url http://127.0.0.1:9222` |
| 查看登录态状态 | `cookie-status` |
| 热门榜 + 关键词雷达 | `radar --keyword "AI 大模型"` |
| 检查 UP 主新投稿 | `subscribe-check --config config.json --state state.json` |
| 直播间状态快照 | `live-snapshot --room-id 6` |
| 直播弹幕监听 | `live-danmaku --room-id 6 --seconds 60` |
| 多 BV 合集处理计划 | `collection-plan BVxxxx BVyyyy` |
| 术语表修复转录 | `polish-transcript --input transcript.txt --glossary glossary.json` |

## 可选环境变量

| 变量 | 用途 |
|------|------|
| `OPENCLI_CMD` | 指定 `opencli.cmd` 路径；未设置时自动从 `PATH` 查找。 |
| `BILIBILI_DISABLE_OPENCLI` | 设置为 `1` 时跳过 opencli，直接使用公开 API 兜底。 |
| `BILIBILI_OUTPUT_DIR` | 下载和转录输出目录。 |
| `BILIBILI_COOKIE` | 明文 Cookie；优先级最高，适合临时注入。 |
| `BILIBILI_COOKIE_STATE` | Cookie state JSON 路径；默认 `.runtime\bilibili-cookie-state.json`。 |
| `BILIBILI_CDP_URL` | 已启动 Chrome DevTools 端口，例如 `http://127.0.0.1:9222`。 |
| `BILIBILI_CHROME_PROFILE` | `chrome-login` 使用的可复用 Chrome 用户目录。 |
| `WHISPER_DOWNLOAD_ROOT` | faster-whisper 模型下载缓存目录。 |
| `WHISPER_MODEL_NAME` | 没有本地模型时自动使用的模型名，默认 `tiny`。 |

## 注意

- B 站搜索接口偶发返回空列表，skill 的公开 API 兜底已内置重试。
- Windows PowerShell 传中文参数前可先执行 `chcp 65001`，也可使用英文关键词、UID、BV 避免编码影响。
- `--find-video` 是“站内搜索找指定视频”的自动化入口；`--bvid` 是“已知 BV 后直接处理”的入口，两者用途不同。
- 默认在笔记生成后清理本次处理产生的音频/视频、转录文本和临时目录，并释放 ASR 模型内存；调试或留证据时加 `--keep-cache`。
