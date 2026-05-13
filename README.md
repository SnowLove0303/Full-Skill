# Full-Skill

Version: V3

Reusable skill collection for Codex/OpenClaw agents. Current focus:

- `bilibili-all-in-one-2026-04-18-v2`: Bilibili search/download/transcribe/note workflow.
- `bilibili-all-in-one-2026-04-18-v2/scripts/juya-daily`: strict Juya daily-video full flow, built for OpenClaw scheduled agents and local verification.

## V3 Highlights

- Strict latest-video gate for Juya: only accepts videos verified by Bilibili `x/web-interface/view`, `owner.mid=285286947`, AI daily title, target date, newest `pubdate`.
- Reusable path resolution: scripts can run inside an OpenClaw agent workspace or from a cloned repo on another device.
- Default runtime output stays under `F:\AIAPP\Xiangmu\MutiAgent\runtime\bilibili-fullflow` on this machine; override with `BILIBILI_FULLFLOW_RUNTIME_ROOT`.
- Notion publishing updates an existing page with the same BVID/title when found; otherwise it creates a new daily page.
- No token or cookie is stored in this repo. Use environment variables or local OpenClaw workspace config.

## Quick Start

```powershell
cd F:\AIAPP\Xiangmu\MutiAgent\Full-Skill\bilibili-all-in-one-2026-04-18-v2
.\scripts\setup.ps1 -RunSmokeTest
```

Strict Juya lookup only:

```powershell
.\scripts\juya-daily\find-juya-today-daily.ps1
```

Full flow:

```powershell
$env:OPENCLAW_AGENT_WORKSPACE = "F:\AIAPP\Openclaw\agents\bilibili-skill-runner\workspace"
$env:JUYA_WRITE_NOTION = "1"
.\scripts\juya-daily\run-juya-today-fullflow.ps1
```

Docs:

- [Juya daily V3 usage](bilibili-all-in-one-2026-04-18-v2/docs/JUYA_DAILY_V3.md)
- [OpenClaw agent prompt](bilibili-all-in-one-2026-04-18-v2/docs/OPENCLAW_AGENT_PROMPT.md)
- [New device reuse guide](bilibili-all-in-one-2026-04-18-v2/docs/REUSE_ON_NEW_DEVICE.md)
