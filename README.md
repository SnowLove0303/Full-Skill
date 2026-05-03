# Full-Skill

Personal Codex skill collection.

## Skills

### bilibili-all-in-one-2026-04-18-v2

Bilibili workflow skill for:

- Searching Bilibili videos and UP creators.
- Listing latest UP videos.
- Downloading video/audio through `opencli` where available.
- Falling back to Bilibili public APIs for search and UP video discovery.
- Transcribing downloaded media and generating structured daily notes.

Path:

```text
bilibili-all-in-one-2026-04-18-v2/
```

Quick smoke test:

```powershell
python .\bilibili-all-in-one-2026-04-18-v2\scripts\bilibili-opencli\scripts\run.py --search "橘鸦Juya" --limit 3 --dry-run
```

Optional UP-list test, best with `OPENCLI_CMD` configured because Bilibili may block anonymous signed space APIs:

```powershell
python .\bilibili-all-in-one-2026-04-18-v2\scripts\bilibili-opencli\scripts\run.py --uid 285286947 --limit 3 --dry-run
```
