# Bilibili Expander Module

本模块是 `bilibili-all-in-one` 的扩展工具箱，不是独立 Codex Skill。它把视频证据包、弹幕、关键帧、订阅监控、内容雷达、直播快照、直播弹幕监听、下载后端探测、转录修复和轻量工具服务统一到一个 CLI。

## 入口

```powershell
$Skill = "F:\AIAPP\Codex\.codex\skills\bilibili-all-in-one-2026-04-18-v2"
$Expander = "$Skill\scripts\bilibili-expander\cli.py"
python $Expander --help
```

## 功能

- `evidence-pack`：生成视频证据包，包含 `metadata.json`、`subtitles.json`、`danmaku.json`、`danmaku.ass`、`sectioned.md`、`smoke-report.json`，如果本地有媒体或启用下载，还会抽取 `frames/*.jpg`。
- `danmaku`：抓取视频弹幕 JSON。
- `subtitle`：抓取官方字幕 JSON。
- `download`：按 `BBDown -> yutto -> yt-dlp -> python -m yt_dlp` 顺序自动选择下载后端。
- `backends`：显示当前可用下载后端。
- `radar`：生成排行榜 + 关键词搜索内容雷达。
- `subscribe-check`：按配置检查 UP 主新投稿，生成增量报告并维护 state。
- `live-snapshot`：获取直播间当前标题、状态、分区、在线人数等快照。
- `live-danmaku`：无第三方依赖连接 B 站直播弹幕 WebSocket，保存实时弹幕 JSONL 和 Markdown 摘要。
- `collection-plan`：把多个 BV/URL 整理成合集处理计划。
- `polish-transcript`：按术语表修复和规范化转录文本。
- `mcp-stdio`：启动本地 JSON-lines 工具服务，供 Agent 以工具方式读取视频信息、字幕、弹幕和后端状态。

## 示例

```powershell
# 生成证据包，不下载媒体，只抓元数据/字幕/弹幕
python $Expander evidence-pack --bvid BVxxxx --output E:\MorenAnzhuangLujing\Huangjingdajian\downloads\bilibili\evidence

# 下载并抽关键帧
python $Expander evidence-pack --bvid BVxxxx --download --backend auto --every-seconds 30 --frame-limit 24

# 内容雷达
python $Expander radar --keyword "AI 大模型" --keyword "OpenAI" --limit 10 --output "$env:TEMP\bilibili-radar.md"

# UP 主订阅增量检查
python $Expander subscribe-check --config ".\subscriptions.example.json" --state "$env:TEMP\bilibili-sub-state.json" --output "$env:TEMP\bilibili-sub-report.md"

# 转录术语修复
python $Expander polish-transcript --input transcript.txt --glossary glossary.json

# 直播弹幕监听
python $Expander live-danmaku --room-id 6 --seconds 60 --max-messages 200 --output "$env:TEMP\bilibili-live-danmaku.jsonl"
```

## 订阅配置格式

```json
{
  "limit": 10,
  "users": [
    {"uid": "285286947", "name": "示例UP主"}
  ]
}
```

## MCP JSON-lines 格式

这是轻量本地协议，不声明为完整 MCP SDK 服务器，适合本机 Agent 快速集成：

```json
{"id":"1","tool":"bilibili.video_info","params":{"bvid":"BVxxxx"}}
{"id":"2","tool":"bilibili.subtitles","params":{"bvid":"BVxxxx"}}
{"id":"3","tool":"bilibili.danmaku","params":{"bvid":"BVxxxx"}}
{"id":"4","tool":"bilibili.live_snapshot","params":{"room_id":"6"}}
{"id":"5","tool":"bilibili.backends","params":{}}
```

输出为一行 JSON：

```json
{"id":"1","ok":true,"result":{}}
```
