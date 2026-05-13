# Juya Daily V3

This workflow produces a daily Notion page for 橘鸦Juya AI 早报.

## Flow

1. `find-juya-today-daily.ps1` finds the target video.
2. `run-juya-today-fullflow.ps1` downloads audio, transcribes, writes an Obsidian note, saves a current report, then publishes to Notion.
3. `write-notion-juya-daily.ps1` writes or refreshes the Notion page.

## Quality Gates

- Only accepts videos verified by Bilibili `x/web-interface/view`.
- Requires `owner.mid=285286947`.
- Requires an AI daily title and target date unless `JUYA_REQUIRE_TODAY=0`.
- The Notion writer refuses mojibake titles/body text and stale placeholder report text.
- Existing daily pages are refreshed by BVID/title instead of silently returning `exists`.

## Useful Environment Variables

- `OPENCLAW_AGENT_WORKSPACE`: workspace for lookup/report artifacts.
- `BILIBILI_SKILL_ROOT`: override the skill root when running scripts from outside the repo.
- `BILIBILI_FULLFLOW_RUNTIME_ROOT`: runtime output root.
- `BILIBILI_DAILY_NOTION_DATABASE_ID`: Notion database ID.
- `NOTION_KEY` or `NOTION_TOKEN`: Notion integration token.
- `NOTION_KEY_FILE`: local file containing the Notion token.
