# Full-Skill

Reusable Codex skill collection. Current package:

- `bilibili-all-in-one-2026-04-18-v2`: the single Bilibili entrypoint skill.

## Bilibili All In One

This package merges the former Bilibili skills into one root `SKILL.md`:

- AI news workflow from `scripts/bilibili-news`
- OpenCLI search/download/transcribe/note workflow from `scripts/bilibili-opencli`
- Hot monitor report and email workflow from `scripts/bilibili-hot-monitor`

The old child skill entry files were converted to `MODULE.md` files so Codex discovers only the root Bilibili skill while still keeping module-level documentation.

## Quick Start

```powershell
cd .\bilibili-all-in-one-2026-04-18-v2
.\scripts\setup.ps1 -RunSmokeTest
```

Useful references:

- [Root skill](bilibili-all-in-one-2026-04-18-v2/SKILL.md)
- [Quick reference](bilibili-all-in-one-2026-04-18-v2/quick-ref.md)
- [OpenCLI module](bilibili-all-in-one-2026-04-18-v2/scripts/bilibili-opencli/MODULE.md)
- [Hot monitor module](bilibili-all-in-one-2026-04-18-v2/scripts/bilibili-hot-monitor/MODULE.md)
