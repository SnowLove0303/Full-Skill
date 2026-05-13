# OpenClaw Agent Prompt

Use this as the scheduled agent objective:

```text
Run the Juya daily workflow for today's Asia/Shanghai date. Find the latest 橘鸦Juya AI 早报 video, verify the owner/date/title, download and transcribe it, save the vault note, then publish or refresh the Notion daily page.

If the video cannot be verified, do not publish a page. If transcription succeeds but quality is low, publish with a clear "needs proofreading" note rather than pretending the summary is final.
```

Recommended command:

```powershell
$env:OPENCLAW_AGENT_WORKSPACE = "F:\AIAPP\Openclaw\agents\bilibili-skill-runner\workspace"
$env:JUYA_WRITE_NOTION = "1"
.\scripts\juya-daily\run-juya-today-fullflow.ps1
```
