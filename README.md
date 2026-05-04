# Full-Skill

Personal Codex skill collection.

## Skills

### bilibili-all-in-one-2026-04-18-v2

Bilibili workflow skill for:

- Searching Bilibili videos and UP creators.
- Locating a specific target video through Bilibili site search with filters.
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
.\bilibili-all-in-one-2026-04-18-v2\scripts\setup.ps1 -RunSmokeTest
python .\bilibili-all-in-one-2026-04-18-v2\scripts\bilibili-opencli\scripts\run.py --search "橘鸦Juya" --limit 3 --dry-run
```

Target-video site-search test:

```powershell
python .\bilibili-all-in-one-2026-04-18-v2\scripts\bilibili-opencli\scripts\run.py --find-video "OpenAI OpenClaw AI早报 2026-05-03" --author "橘鸦Juya" --date 2026-05-03 --must OpenClaw --limit 10 --strict-find --dry-run
```

Expected target:

```text
BV1ro9dBFEEB
橘鸦Juya
OpenAI 宣布 ChatGPT 账户可登录 OpenClaw 复用订阅；猎豹移动AI产品被指抄袭开源项目【AI 早报 2026-05-03】
```

Optional UP-list test, best with `OPENCLI_CMD` configured because Bilibili may block anonymous signed space APIs:

```powershell
python .\bilibili-all-in-one-2026-04-18-v2\scripts\bilibili-opencli\scripts\run.py --uid 285286947 --limit 3 --dry-run
```
