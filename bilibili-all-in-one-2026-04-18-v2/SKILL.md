---
name: bilibili-all-in-one
description: Bilibili reusable workflow skill. Provides search, download, transcription, note generation, and V3 strict Juya daily full flow for OpenClaw agents.
triggers:
  - bilibili
  - B站
  - Bilibili skill
  - Juya daily
  - 橘鸦日报
  - AI早报
---

# Bilibili All-in-One V3

This skill is the reusable Bilibili workflow package for Codex/OpenClaw agents.

## Core Capabilities

- Search Bilibili and locate target videos.
- Download audio/video through OpenCLI.
- Transcribe media and generate markdown notes.
- Run Juya daily automation with strict anti-wrong-video validation.
- Publish one Notion daily page per full-flow run when Notion credentials are available.

## Juya Daily Full Flow

Use this path when the task is: find Juya's latest AI daily video for today, process it, and write one Notion daily page.

```powershell
cd <this-skill-root>
$env:OPENCLAW_AGENT_WORKSPACE = "<openclaw-agent-workspace>"
$env:JUYA_WRITE_NOTION = "1"
.\scripts\juya-daily\run-juya-today-fullflow.ps1
```

Lookup only:

```powershell
.\scripts\juya-daily\find-juya-today-daily.ps1
```

## Video Selection Rule

Never rely on generic Bilibili search ranking alone. The V3 selector must verify every candidate through:

- Bilibili API: `https://api.bilibili.com/x/web-interface/view?bvid=<BVID>`
- Author MID exactly `285286947`
- Title contains `AI` and `早报` or `日报`
- Not reposted
- Date matches `JUYA_DAILY_DATE`, or current Asia/Shanghai date by default
- If multiple videos match, choose newest `pubdate`

If validation fails, stop and report `JUYA_FULLFLOW_BLOCKED`.

## Important Environment Variables

| Variable | Purpose |
| --- | --- |
| `OPENCLAW_AGENT_WORKSPACE` | OpenClaw agent workspace for result JSON and local Notion config. |
| `BILIBILI_ALL_IN_ONE_SKILL_ROOT` | Optional explicit skill root. |
| `BILIBILI_FULLFLOW_RUNTIME_ROOT` | Runtime output root. Defaults to `F:\AIAPP\Xiangmu\MutiAgent\runtime\bilibili-fullflow` on the user's machine. |
| `BILIBILI_SKILL_PYTHON` | Python executable for the Bilibili workflow. |
| `OPENCLI_CMD` | OpenCLI executable. |
| `JUYA_DAILY_DATE` | Target date, `YYYY-MM-DD`; defaults to today in Asia/Shanghai. |
| `JUYA_REQUIRE_TODAY` | Set to `0` only for backfill tests. |
| `JUYA_WRITE_NOTION` | Set to `0` to disable Notion publishing. Default is enabled when the publish script exists. |
| `BILIBILI_DAILY_NOTION_DATABASE_ID` | Target Notion database. |
| `BILIBILI_DAILY_NOTION_PAGE_ID` | Optional debug override. If set, update that page; otherwise create a new page per run. |
| `NOTION_KEY` / `NOTION_TOKEN` / `NOTION_API_KEY` | Notion API token. Do not commit tokens. |

## Output Contract

The full-flow command prints:

```text
JUYA_FULLFLOW_OK
BVID=<resolved-bvid>
REPORT=<path-to-json-report>
```

or:

```text
JUYA_FULLFLOW_BLOCKED
REPORT=<path-to-json-report>
```

The JSON report includes lookup evidence, step outputs, artifact paths, and final success status.

## Docs

- `docs/JUYA_DAILY_V3.md`
- `docs/OPENCLAW_AGENT_PROMPT.md`
- `docs/REUSE_ON_NEW_DEVICE.md`
