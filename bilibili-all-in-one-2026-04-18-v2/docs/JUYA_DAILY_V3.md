# Juya Daily V3

## Goal

Run a real end-to-end Bilibili workflow for Juya's daily AI video:

1. Find today's correct Juya video.
2. Refuse wrong videos.
3. Download and transcribe the video.
4. Generate markdown notes.
5. Write one independent Notion daily page for that run.

## Required Local Tools

- Node.js available as `node`.
- PowerShell.
- Python environment for `scripts/bilibili-opencli/scripts/run.py`.
- OpenCLI available by `OPENCLI_CMD` or installed at the known local tool path.
- Notion token from env or `OPENCLAW_AGENT_WORKSPACE\.config\notion\api_key`.

Do not store secrets in this repository.

## Commands

Lookup only:

```powershell
cd F:\AIAPP\Xiangmu\MutiAgent\Full-Skill\bilibili-all-in-one-2026-04-18-v2
.\scripts\juya-daily\find-juya-today-daily.ps1
```

Full flow:

```powershell
cd F:\AIAPP\Xiangmu\MutiAgent\Full-Skill\bilibili-all-in-one-2026-04-18-v2
$env:OPENCLAW_AGENT_WORKSPACE = "F:\AIAPP\Openclaw\agents\bilibili-skill-runner\workspace"
$env:JUYA_WRITE_NOTION = "1"
.\scripts\juya-daily\run-juya-today-fullflow.ps1
```

Backfill a specific date:

```powershell
$env:JUYA_DAILY_DATE = "2026-05-05"
.\scripts\juya-daily\run-juya-today-fullflow.ps1
```

Dry Notion off:

```powershell
$env:JUYA_WRITE_NOTION = "0"
.\scripts\juya-daily\run-juya-today-fullflow.ps1
```

## Correctness Gate

The selector is intentionally strict. It must verify all of these before execution continues:

- `owner.mid` is `285286947`.
- The title contains `AI`.
- The title contains Juya's daily-video keywords for morning report or daily report.
- The title is not a repost.
- Published date matches the target date unless `JUYA_REQUIRE_TODAY=0`.
- If several candidates match, newest `pubdate` wins.

This avoids the recurring failure where generic search returns another creator or an older Juya video.

## Notion Behavior

Default: create one new Notion page per run in `BILIBILI_DAILY_NOTION_DATABASE_ID`.

Only set `BILIBILI_DAILY_NOTION_PAGE_ID` when intentionally updating a known page during debugging. Scheduled OpenClaw jobs should leave it unset.

The page title format is:

```text
Juya AI <YYYY-MM-DD> <BVID>
```

## Runtime Paths

On this machine, default runtime output is:

```text
F:\AIAPP\Xiangmu\MutiAgent\runtime\bilibili-fullflow
```

Override with:

```powershell
$env:BILIBILI_FULLFLOW_RUNTIME_ROOT = "F:\AIAPP\Xiangmu\MutiAgent\runtime\bilibili-fullflow"
```
