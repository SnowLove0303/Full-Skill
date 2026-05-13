# Reuse On A New Device

1. Clone the repo and install the Bilibili skill dependencies with `scripts\setup.ps1`.
2. Set `OPENCLAW_AGENT_WORKSPACE` to a writable agent workspace.
3. Set `NOTION_KEY`, `NOTION_TOKEN`, or `NOTION_KEY_FILE` for Notion publishing.
4. Optional: set `OPENCLI_CMD`, `BILIBILI_SKILL_PYTHON`, and `BILIBILI_SKILL_ROOT` if auto-detection does not match the machine.
5. Run:

```powershell
cd <repo>\bilibili-all-in-one-2026-04-18-v2
.\scripts\juya-daily\run-juya-today-fullflow.ps1
```

No cookies or tokens are committed to this repo. Keep login state, Notion keys, and browser cookies in the local workspace or environment variables.
