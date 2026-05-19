---
name: zhihu-search-info
description: Search Zhihu and retrieve structured information from Zhihu questions, answers, articles, columns, users, and search result pages through a logged-in Chrome/ChromeDidy CDP session. Use when the user asks to search Zhihu, inspect Zhihu content, gather answer/article evidence, summarize Zhihu discussions, or automate authenticated Zhihu browsing without copying cookies.
---

# Zhihu Search Info

Use this skill when the task needs Zhihu search or page information. Prefer a logged-in ChromeDidy profile over anonymous HTTP scraping because Zhihu frequently changes rendering, rate limits anonymous access, and may hide content behind login or verification.

## Core Workflow

1. Check whether ChromeDidy is available and whether a logged-in CDP port is already running.
2. Use `scripts/zhihu_cdp.ps1` for search or page extraction.
3. Keep raw evidence local as JSON/Markdown; summarize to the user from the extracted fields.
4. If login or CAPTCHA blocks extraction, stop with the blocker and ask the operator to complete login/verification in the visible Chrome window.

Typical commands:

```powershell
powershell -ExecutionPolicy Bypass -File F:/AIAPP/Codex/.codex/skills/zhihu-search-info/scripts/zhihu_cdp.ps1 `
  -Mode search `
  -Query "AI daily report" `
  -Type answer `
  -Limit 8 `
  -OutJson ".omx/state/zhihu/search.json"
```

```powershell
powershell -ExecutionPolicy Bypass -File F:/AIAPP/Codex/.codex/skills/zhihu-search-info/scripts/zhihu_cdp.ps1 `
  -Mode fetch `
  -Url "https://www.zhihu.com/question/123456789" `
  -OutJson ".omx/state/zhihu/question.json" `
  -OutMarkdown ".omx/state/zhihu/question.md"
```

```powershell
powershell -ExecutionPolicy Bypass -File F:/AIAPP/Codex/.codex/skills/zhihu-search-info/scripts/zhihu_cdp.ps1 `
  -Mode answer `
  -Url "https://www.zhihu.com/question/123456789/answer/987654321" `
  -MaxContent 8000 `
  -OutJson ".omx/state/zhihu/answer.json"
```

## Browser And Login Rules

- Use the `chrome-control-suite` skill first when Chrome/CDP readiness is uncertain.
- Prefer `CHROME_DIDY_CDP_URL` or `CHROME_DIDY_CHROME_PORT`; otherwise the script falls back to `http://127.0.0.1:9222`.
- Preserve any existing logged-in Zhihu tab/profile as the source of truth. Probe with `-Mode observe` first when a Zhihu tab is already open, and avoid `-NewTab` unless navigation would disturb the user's current work.
- Run navigation modes serially when reusing the same existing tab. If multiple Zhihu captures must run at once, pass `-NewTab` so parallel workers do not interrupt each other's `page.goto` calls.
- Do not launch an ephemeral or fresh Chrome profile for authenticated Zhihu tasks. The active environment may already expose a logged-in session through `http://127.0.0.1:9223`.
- Do not export, paste, or store Zhihu cookies. Login state belongs in the durable Chrome profile.
- Use a visible Chrome profile when the page asks for login, slider verification, phone verification, or CAPTCHA.
- Treat extraction results as evidence snapshots, not stable APIs. Re-run extraction before citing fast-changing pages.

## Modes

- `search`: opens Zhihu search, then queries `search_v3` from the logged-in browser context. Supports `-Type all|answer|article|question`; falls back to DOM cards when the API path is sparse or unavailable.
- `question`: opens a question and retrieves answer rows through the logged-in browser context. Supports `-Sort default|created`.
- `answer`: opens an answer URL/id and retrieves full answer detail, author, votes, comments, timestamps, and question URL.
- `article`: opens a Zhuanlan article and extracts title, author, publish hint, text, and image URLs from the rendered page.
- `fetch`: opens a Zhihu URL and chooses the best extractor from the page type: question API, answer API, article DOM, or generic DOM fallback.
- `hot`: opens Zhihu hot/trending and reads the hot-list API from the logged-in browser context.
- `recommend`: opens the logged-in home page and reads the recommendation feed API.
- `observe`: captures the current active Zhihu page without navigation.

## Prior Art Integration

- OpenCLI's Zhihu adapter is the main reference for the current implementation: it calls Zhihu JSON endpoints from inside the browser with `credentials: "include"`, so the durable Chrome profile provides login state without copying cookies.
- Keep write actions such as follow, like, favorite, comment, or answer outside this skill unless the user explicitly asks for a separate write-capable workflow. This skill is for search, retrieval, and evidence capture.

## Quality Bar

For user-facing summaries, include the source URL for each major claim. If results are sparse, blocked, or mostly generic snippets, say so and do not overstate coverage.

Use `references/prior-art.md` when deciding whether to use OpenCLI/qiaomu workflows, old API wrappers, or ChromeDidy extraction.
