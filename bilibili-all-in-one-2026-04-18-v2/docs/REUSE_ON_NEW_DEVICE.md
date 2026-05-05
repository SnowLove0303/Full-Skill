# Reuse On A New Device

## 1. Clone

```powershell
git clone https://github.com/SnowLove0303/Full-Skill.git <target-dir>
cd <target-dir>\bilibili-all-in-one-2026-04-18-v2
```

## 2. Install/Check Dependencies

```powershell
.\scripts\setup.ps1 -RunSmokeTest
```

If using an existing Python/OpenCLI installation, set:

```powershell
$env:BILIBILI_SKILL_PYTHON = "<python.exe>"
$env:OPENCLI_CMD = "<opencli.cmd>"
```

## 3. Connect OpenClaw

Set the agent workspace before running:

```powershell
$env:OPENCLAW_AGENT_WORKSPACE = "<OpenClaw agent workspace>"
```

The workspace is used for lookup JSON, fullflow JSON, and optional local Notion config.

## 4. Connect Notion

Use one of:

```powershell
$env:NOTION_TOKEN = "<token>"
```

or create:

```text
<OpenClaw agent workspace>\.config\notion\api_key
```

Do not commit token files.

## 5. Run

```powershell
.\scripts\juya-daily\run-juya-today-fullflow.ps1
```

Set `JUYA_WRITE_NOTION=0` for a local-only verification run.

## 6. Troubleshooting

- Wrong video: inspect `juya-today-daily-result.json`; execution should be blocked if `validation.eligible` is false.
- Bilibili cookie required: `bilibili-update-viewer` may need `BILIBILI_COOKIES`, but the Juya V3 selector uses public search plus view API.
- Notion failed: check database access and title property; the token must have access to the target database.
