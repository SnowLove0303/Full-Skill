# Zhihu Prior Art

This skill should start from existing tools where possible, then fall back to ChromeDidy extraction when login state or dynamic rendering matters.

## Useful Existing Projects

- OpenCLI browser adapter for Zhihu: `https://opencli.info/docs/adapters/browser/zhihu.html`
- OpenCLI repository: `https://github.com/jackwener/opencli`
- OpenCLI skill collection: `https://github.com/joeseesun/opencli-skill`
- Qiaomu OpenCLI skills: `https://github.com/joeseesun/qiaomu-opencli-skills`
- Historical Python OAuth/API wrapper: `https://pypi.org/project/zhihu-oauth/` (the original GitHub repository is no longer publicly accessible, so treat it only as historical context)

Local review snapshot:

- OpenCLI clone: `F:\AIAPP\Codex\Codex1\.tmp\prior-art\opencli`
- Reviewed commit: `8182ffb chore(deps): bump tsx from 4.21.0 to 4.22.2 (#1663)`
- Relevant files: `clis/zhihu/search.js`, `question.js`, `answer-detail.js`, `hot.js`, `recommend.js`, `download.js`

## Recommendation

Use OpenCLI/Qiaomu when it is already installed and the task maps directly to its adapter commands. The strongest pattern to reuse is OpenCLI's browser-context API access: navigate with a logged-in browser, then call Zhihu JSON endpoints with `fetch(..., { credentials: "include" })`. This preserves login state without exporting cookies.

Use this skill's ChromeDidy CDP script when:

- the task needs the user's logged-in Zhihu state;
- search or answer rendering differs from the old API wrappers;
- the user needs evidence from the rendered page;
- a reusable Codex skill entry point is preferred.

Avoid making old unofficial API wrappers the primary path. They are useful references for URL patterns and object concepts, but many Zhihu endpoints and authentication expectations have changed over time.

## Adopted Patterns

- `search`: `https://www.zhihu.com/api/v4/search_v3`
- `question`: `https://www.zhihu.com/api/v4/questions/{questionId}/answers`
- `answer`: `https://www.zhihu.com/api/v4/answers/{answerId}`
- `hot`: `https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total`
- `recommend`: `https://www.zhihu.com/api/v3/feed/topstory/recommend`
- `article`: rendered Zhuanlan DOM extraction, based on OpenCLI's article download selectors

## Search Terms For Future Updates

- `site:github.com zhihu search scraper playwright`
- `site:github.com zhihu spider answer question`
- `site:github.com OpenCLI Zhihu`
- `site:github.com zhihu_oauth`
