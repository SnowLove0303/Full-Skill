#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const WORKSPACE = process.env.OPENCLAW_AGENT_WORKSPACE || process.cwd();
const DEFAULT_LOOKUP_RESULT = path.join(WORKSPACE, 'juya-today-daily-result.json');
const DEFAULT_REPORT = path.join(WORKSPACE, 'juya-today-fullflow-report.json');
const DEFAULT_DATABASE_ID = '34d003b68bec8027a6eafd8b918c72c5';
const NOTION_VERSION = process.env.NOTION_VERSION || '2022-06-28';
const JUYA_MID = '285286947';
const MOJIBAKE_RE = /[�閺閿鏃鏁瑙鏈杞鐐锛銆聽]/;
const BAD_PLACEHOLDER_RE = /(等待转录结果|本次查询未返回结构化时间轴|未返回结构化时间轴)/;

function parseArgs(argv) {
  const args = { dryRun: false };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--dry-run' || arg === '-n') {
      args.dryRun = true;
    } else if (arg.startsWith('--')) {
      const key = arg.slice(2).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      const next = argv[i + 1];
      args[key] = next && !next.startsWith('--') ? argv[++i] : true;
    }
  }
  return args;
}

function die(message, code = 1) {
  console.error(message);
  process.exit(code);
}

function readJson(filePath, label) {
  if (!fs.existsSync(filePath)) die(`${label} not found: ${filePath}`);
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8').replace(/^\uFEFF/, ''));
  } catch (error) {
    die(`${label} is not valid JSON: ${error.message}`);
  }
}

function readText(filePath) {
  if (!filePath || !fs.existsSync(filePath)) return '';
  return fs.readFileSync(filePath, 'utf8').replace(/^\uFEFF/, '').trim();
}

function readKey() {
  if (process.env.NOTION_KEY?.trim()) return process.env.NOTION_KEY.trim();
  if (process.env.NOTION_TOKEN?.trim()) return process.env.NOTION_TOKEN.trim();

  const candidates = [
    process.env.NOTION_KEY_FILE,
    path.join(WORKSPACE, '.config', 'notion', 'api_key'),
    path.join(os.homedir(), '.config', 'notion', 'api_key')
  ].filter(Boolean);

  for (const candidate of candidates) {
    try {
      const value = fs.readFileSync(candidate, 'utf8').split(/\r?\n/)[0].trim();
      if (value) return value;
    } catch {
      // Keep trying the known key locations.
    }
  }

  die(`Missing Notion API key. Checked: ${candidates.join('; ')}`);
}

async function notionFetch(url, { method = 'GET', body } = {}) {
  const response = await fetch(url, {
    method,
    headers: {
      Authorization: `Bearer ${readKey()}`,
      'Content-Type': 'application/json',
      'Notion-Version': NOTION_VERSION
    },
    body: body === undefined ? undefined : JSON.stringify(body)
  });

  const text = await response.text();
  let json;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    json = { raw: text };
  }

  if (!response.ok) {
    die(JSON.stringify({ error: true, status: response.status, url, response: json }, null, 2));
  }
  return json;
}

function compactSpaces(text) {
  return String(text ?? '').replace(/\s+/g, ' ').trim();
}

function plainText(text) {
  const value = compactSpaces(text);
  return value.length > 1900 ? `${value.slice(0, 1890)}...` : value;
}

function richText(text) {
  return [{ type: 'text', text: { content: plainText(text) } }];
}

function block(type, text) {
  return { object: 'block', type, [type]: { rich_text: richText(text) } };
}

function bullet(text) {
  return block('bulleted_list_item', text);
}

function para(text) {
  return block('paragraph', text);
}

function heading(level, text) {
  return block(`heading_${level}`, text);
}

function statValue(value) {
  return value === undefined || value === null || value === '' ? '接口未返回' : value;
}

function normalizeVideo(lookup) {
  const video = lookup?.result;
  if (!video?.bvid) die('Lookup result does not contain a video BVID.');
  if (String(video.mid || '') !== JUYA_MID) die(`Latest video owner mismatch: ${video.mid || 'unknown'}`);

  const title = String(video.title || '');
  if (!/(AI|人工智能)/i.test(title) || !/(早报|日报)/.test(title)) {
    die(`Latest Juya video is not recognized as an AI daily: ${title}`);
  }

  return {
    bvid: String(video.bvid),
    title,
    author: String(video.author || '橘鸦Juya'),
    mid: String(video.mid || JUYA_MID),
    description: String(video.description || video.desc || ''),
    url: String(video.url || `https://www.bilibili.com/video/${video.bvid}`),
    publishedDate: String(video.published_date || lookup.target_date || ''),
    publishedAt: String(video.published_at || ''),
    durationText: video.duration_text || video.duration || '',
    view: video.view ?? video.stat?.view,
    like: video.like ?? video.stat?.like,
    favorite: video.favorite ?? video.stat?.favorite,
    coin: video.coin ?? video.stat?.coin,
    source: String(lookup.source_priority || lookup.source || video.source || 'lookup_verified'),
    timeline: extractTimeline(video)
  };
}

function extractTimeline(video) {
  const text = [video.description, video.desc, video.dynamic].filter(Boolean).join('\n');
  const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const timeline = [];

  for (const line of lines) {
    const match = line.match(/^(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$/);
    if (match) {
      timeline.push({ time: match[1], topic: cleanTopic(match[2]) });
    }
  }

  return timeline;
}

function listArtifactPaths(report, key, extensionRe) {
  return (report?.[key] || [])
    .map((item) => String(item.FullName || item.fullName || item.path || ''))
    .filter((filePath) => filePath && extensionRe.test(filePath) && fs.existsSync(filePath));
}

function collectArtifacts(report) {
  const notePath = listArtifactPaths(report, 'noteArtifacts', /\.md$/i)[0] || '';
  const transcriptPath =
    listArtifactPaths(report, 'downloadArtifacts', /_transcript\.txt$/i)[0] ||
    listArtifactPaths(report, 'noteArtifacts', /_transcript\.txt$/i)[0] ||
    '';

  return {
    notePath,
    transcriptPath,
    noteText: readText(notePath),
    transcriptText: readText(transcriptPath)
  };
}

function stripFrontmatter(markdown) {
  return markdown.replace(/^---[\s\S]*?---\s*/, '').trim();
}

function cleanTopic(text) {
  return compactSpaces(text)
    .replace(/^[-*⬛️\d.、]+/, '')
    .replace(/^Intro:?$/i, '开场')
    .replace(/^Outro:?$/i, '收尾');
}

function cleanTranscriptText(text) {
  const replacements = [
    [/German Intelligence|Germany Intelligence|Gem93\.1|Gemony/gi, 'Gemini Intelligence'],
    [/Gerna AI|Gerna embedding/gi, 'Jina AI embedding'],
    [/Support AI|Support Mark/gi, 'Sapient AI / Sapient Mark'],
    [/Agence/gi, 'Agent'],
    [/AIAZEMS|AZEMS|AZEMO/gi, 'AI Agents'],
    [/Rizanning/gi, 'reasoning'],
    [/Mite's/gi, 'Mythos'],
    [/Shapify/gi, 'Shopify'],
    [/Affabet/gi, 'Alphabet'],
    [/Iceomorph/gi, 'Isomorphic Labs'],
    [/CloudCowork/gi, 'Claude Code'],
    [/Cloud for Legal/gi, 'Claude for Legal'],
    [/\bGermany\b/gi, 'Gemini']
  ];

  let value = compactSpaces(text);
  for (const [pattern, replacement] of replacements) {
    value = value.replace(pattern, replacement);
  }
  return value;
}

function isLowSignalTranscriptLine(line) {
  return /^(各位观众|今天是|欢迎收看|屏幕上是|接下来请看|今天的资讯|明天见)/.test(line) ||
    /主要内容接下来请看详细报道$/.test(line);
}

function truncateTopic(line) {
  return line.length > 120 ? `${line.slice(0, 118)}...` : line;
}

function transcriptPoints(transcriptText) {
  if (!transcriptText) return [];

  const anchors = [
    'Google', 'Claude', 'Jina', 'Sapient', 'OpenAI', '安全机构', 'Manus', 'DeepMind',
    '豆包', 'Shopify', 'AIQ', 'Alphabet', 'Codex', 'Android', '针对短视频'
  ];
  let text = cleanTranscriptText(transcriptText);
  for (const anchor of anchors) {
    text = text.replace(new RegExp(`(?<!^)(?=${anchor})`, 'g'), '\n');
  }

  return text
    .split(/\n|(?<=[。！？])/)
    .map((line) => cleanTopic(line))
    .filter((line) => line.length >= 18)
    .filter((line) => !isLowSignalTranscriptLine(line))
    .map(truncateTopic)
    .filter((line, index, lines) => lines.indexOf(line) === index)
    .slice(0, 16);
}

function ruleBasedTopics(video, transcriptText) {
  const haystack = cleanTranscriptText([video.title, video.description, transcriptText].join('\n'));
  const rules = [
    {
      re: /Gemini Intelligence|Android/i,
      topic: 'Google 推出 Gemini Intelligence，为部分 Android 设备引入主动式 AI、跨应用与多步骤任务能力。'
    },
    {
      re: /Claude Opus 4\.7|Claude Code/i,
      topic: 'Claude Opus 4.7 快速模式上线 API 与 Claude Code，并开放给多款第三方工具。'
    },
    {
      re: /Jina AI embedding|通用.*模型/i,
      topic: 'Jina AI 发布支持文本、图像、音频与视频的通用 embedding 模型，主打多模态检索能力。'
    },
    {
      re: /Sapient Mark|Sapient AI/i,
      topic: 'Sapient AI 发布面向视频与复杂推理任务的 Sapient Mark 1，并强调开放 API 与低成本。'
    },
    {
      re: /reasoning|400 错误|完整回传/i,
      topic: '部分 Agent API 调用要求完整回传 reasoning/工具调用上下文，否则会触发 400 错误。'
    },
    {
      re: /供应链攻击|AI开发者|CI/i,
      topic: '安全机构预警面向 AI 开发者的供应链攻击，风险集中在 CI、包依赖与开发凭证链路。'
    },
    {
      re: /Computer Use|MacOS后台|Manus/i,
      topic: 'Manus 类工具推进 macOS 后台 Computer Use，让代理可在后台控制桌面任务。'
    },
    {
      re: /AI Pointer|Google AI Studio|DeepMind/i,
      topic: 'Google DeepMind 展示 AI Pointer 实验，可用手势、语音和自然语言直接指挥屏幕任务。'
    },
    {
      re: /Claude for Legal|MCP/i,
      topic: 'Claude for Legal 相关能力扩展到法律场景，并结合 MCP 连接器增强工作流接入。'
    },
    {
      re: /豆包输入法|语音输入法/i,
      topic: '豆包输入法 Mac 版上线，AI 语音输入继续向系统级日常输入场景延伸。'
    },
    {
      re: /AI Agents|长期运行|暂停恢复|上下文/i,
      topic: 'Google 发布长期运行 AI Agents 技术指南，重点是暂停、恢复与上下文保留。'
    },
    {
      re: /Mythos|漏洞|报告/i,
      topic: '社区继续评估 Mythos 类安全报告质量，重点关注漏洞真实性与营销噪声。'
    },
    {
      re: /Shopify|消费者|客单价/i,
      topic: 'Shopify 早期数据显示 AI 引流用户转化与客单价高于自然搜索流量。'
    },
    {
      re: /AIQ|IQ|EQ/i,
      topic: 'AIQ 项目尝试用公开数据估算主流模型 IQ、EQ 与成本效益曲线。'
    },
    {
      re: /AI生成|内容标注|短视频/i,
      topic: '短视频平台将加强 AI 生成内容标注，发布前需选择对应标签。'
    },
    {
      re: /Isomorphic Labs|21 亿美元|药物/i,
      topic: 'Alphabet 旗下 Isomorphic Labs 完成大额融资，继续推进 AI 药物设计与临床管线。'
    },
    {
      re: /Chrome|Agent.*浏览|Nano Banana/i,
      topic: 'Android 版 Chrome 将引入 Gemini 驱动的 Agent 浏览体验，覆盖自动浏览等能力。'
    },
    {
      re: /Codex|每周四|发布节奏/i,
      topic: 'Codex 团队考虑建立更稳定的版本发布节奏，可能以每周四作为较大更新窗口。'
    }
  ];

  return rules
    .filter((rule) => rule.re.test(haystack))
    .map((rule) => rule.topic);
}

function markdownBullets(markdown) {
  return stripFrontmatter(markdown)
    .split(/\r?\n/)
    .map((line) => cleanTopic(line.replace(/^[-*]\s+/, '')))
    .filter((line) => line.length >= 12)
    .filter((line) => !line.startsWith('来源:') && !line.startsWith('_由 OpenCLI'))
    .slice(0, 12);
}

function titleTopic(title) {
  return title.replace(/【.*?】/g, '').trim();
}

function buildInsights(video, artifacts) {
  const timelineTopics = video.timeline.map((item) => item.topic).filter(Boolean);
  const ruleTopics = ruleBasedTopics(video, artifacts.transcriptText);
  const transcriptTopics = transcriptPoints(artifacts.transcriptText);
  const noteTopics = markdownBullets(artifacts.noteText);
  const topicPool = [...ruleTopics, ...timelineTopics, ...transcriptTopics, ...noteTopics]
    .map(cleanTopic)
    .filter((item) => item.length >= 8)
    .filter((item) => !isLowSignalTranscriptLine(item))
    .filter((item, index, items) => items.indexOf(item) === index);

  const highlights = topicPool.slice(0, 8);
  if (highlights.length === 0) {
    highlights.push(`${titleTopic(video.title)}：已核对视频源，等待后续人工补充正文。`);
  }

  const timeline = video.timeline.length
    ? video.timeline.map((item) => `${item.time} ${item.topic}`)
    : topicPool.slice(0, 10).map((item, index) => `主题 ${index + 1}：${item}`);

  const summary = artifacts.transcriptText || artifacts.noteText
    ? `本期主题是“${titleTopic(video.title)}”。已读取本地转录/笔记产物，并从视频标题、转录粗稿与可用简介中整理出重点；转录存在同音词误识别，页面保留“需校对”标记，避免把低置信内容包装成定稿。`
    : `本期主题是“${titleTopic(video.title)}”。当前仅完成视频核对，正文需要等待转录或 B 站简介时间轴补齐。`;

  return {
    highlights,
    timeline,
    summary,
    evidenceLevel: artifacts.transcriptText && artifacts.noteText
      ? 'note_and_transcript'
      : artifacts.transcriptText
        ? 'transcript_only'
        : artifacts.noteText
          ? 'note_only'
          : 'lookup_only'
  };
}

function buildPage(video, report) {
  const artifacts = collectArtifacts(report);
  const insights = buildInsights(video, artifacts);
  const pageTitle = `橘鸦Juya AI早报 ${video.publishedDate} - ${video.bvid}`;
  if (MOJIBAKE_RE.test(pageTitle)) die(`Page title looks mojibake: ${pageTitle}`);

  const blocks = [
    heading(1, '视频核对'),
    bullet('状态：已核对为橘鸦Juya 当日最新 AI 早报'),
    bullet(`BV号：${video.bvid}`),
    bullet(`链接：${video.url}`),
    bullet(`UP主：${video.author}（UID：${video.mid}）`),
    bullet(`标题：${video.title}`),
    bullet(`发布时间：${video.publishedAt || video.publishedDate}`),
    bullet(`视频时长：${statValue(video.durationText)}`),
    bullet(`B站数据：播放 ${statValue(video.view)} / 点赞 ${statValue(video.like)} / 收藏 ${statValue(video.favorite)} / 投币 ${statValue(video.coin)}`),
    bullet(`查找来源：${video.source}`),
    heading(1, '今日摘要'),
    para(insights.summary),
    heading(1, '重点速览'),
    ...insights.highlights.map((item) => bullet(item)),
    heading(1, '时间轴文本'),
    ...insights.timeline.map((item) => bullet(item)),
    heading(1, '可跟进事项'),
    ...insights.highlights.slice(0, 5).map((item) => bullet(`跟进：${item} 的官方公告、版本号、链接和对开发工作流的影响。`)),
    heading(1, '证据与产物'),
    bullet(`内容证据等级：${insights.evidenceLevel}`),
    bullet(`本地笔记：${artifacts.notePath ? path.basename(artifacts.notePath) : '本次未生成或 report 未携带'}`),
    bullet(`本地转录：${artifacts.transcriptPath ? path.basename(artifacts.transcriptPath) : '本次未生成或 report 未携带'}`),
    heading(1, '转录说明'),
    para('本页由 OpenClaw 的 bilibili-skill-runner 生成：先锁定橘鸦Juya 当日 AI 早报，再执行下载、转录、笔记落盘和 Notion 写入。'),
    para('本次调教后，写入器会优先读取当前 fullflow report 的笔记/转录产物，发现旧页面会直接刷新正文，并拒绝写入乱码标题或“等待转录”类占位日报。')
  ];

  const pageText = blocks.map((item) => item[item.type]?.rich_text?.[0]?.text?.content || '').join('\n');
  if (MOJIBAKE_RE.test(pageText)) die('Generated page text looks mojibake; aborting before Notion write.');
  if ((artifacts.transcriptText || artifacts.noteText) && BAD_PLACEHOLDER_RE.test(pageText)) {
    die('Generated page still contains stale placeholder text while artifacts exist.');
  }

  return {
    pageTitle,
    blocks,
    quality: {
      evidenceLevel: insights.evidenceLevel,
      hasNote: Boolean(artifacts.noteText),
      hasTranscript: Boolean(artifacts.transcriptText),
      blockCount: blocks.length
    }
  };
}

async function findTitleProperty(databaseId) {
  const database = await notionFetch(`https://api.notion.com/v1/databases/${databaseId}`);
  for (const [name, property] of Object.entries(database.properties || {})) {
    if (property.type === 'title') return name;
  }
  die(`No title property found in database ${databaseId}`);
}

async function findExistingPage(databaseId, titleProperty, pageTitle, bvid) {
  const body = {
    page_size: 5,
    filter: {
      or: [
        { property: titleProperty, title: { equals: pageTitle } },
        { property: titleProperty, title: { contains: bvid } }
      ]
    }
  };
  const result = await notionFetch(`https://api.notion.com/v1/databases/${databaseId}/query`, { method: 'POST', body });
  return result.results?.[0] || null;
}

async function createPage(databaseId, titleProperty, pageTitle, blocks) {
  const payload = {
    parent: { database_id: databaseId },
    icon: { type: 'emoji', emoji: '📰' },
    properties: {
      [titleProperty]: {
        title: [{ type: 'text', text: { content: pageTitle } }]
      }
    },
    children: blocks.slice(0, 100)
  };
  return notionFetch('https://api.notion.com/v1/pages', { method: 'POST', body: payload });
}

async function updatePageTitle(pageId, titleProperty, pageTitle) {
  return notionFetch(`https://api.notion.com/v1/pages/${pageId}`, {
    method: 'PATCH',
    body: {
      icon: { type: 'emoji', emoji: '📰' },
      properties: {
        [titleProperty]: {
          title: [{ type: 'text', text: { content: pageTitle } }]
        }
      }
    }
  });
}

async function listBlockChildren(blockId) {
  const children = [];
  let startCursor;
  do {
    const url = new URL(`https://api.notion.com/v1/blocks/${blockId}/children`);
    url.searchParams.set('page_size', '100');
    if (startCursor) url.searchParams.set('start_cursor', startCursor);
    const result = await notionFetch(url.toString());
    children.push(...(result.results || []));
    startCursor = result.has_more ? result.next_cursor : undefined;
  } while (startCursor);
  return children;
}

async function archiveChildren(blockId) {
  const children = await listBlockChildren(blockId);
  for (const child of children) {
    await notionFetch(`https://api.notion.com/v1/blocks/${child.id}`, {
      method: 'PATCH',
      body: { archived: true }
    });
  }
  return children.length;
}

async function appendChildren(blockId, blocks) {
  let appended = 0;
  for (let i = 0; i < blocks.length; i += 100) {
    const chunk = blocks.slice(i, i + 100);
    await notionFetch(`https://api.notion.com/v1/blocks/${blockId}/children`, {
      method: 'PATCH',
      body: { children: chunk }
    });
    appended += chunk.length;
  }
  return appended;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const lookupPath = args.lookupResult || process.env.JUYA_LOOKUP_RESULT || DEFAULT_LOOKUP_RESULT;
  const reportPath = args.report || process.env.BILIBILI_FULLFLOW_REPORT || DEFAULT_REPORT;
  const databaseId = args.databaseId || process.env.BILIBILI_DAILY_NOTION_DATABASE_ID || DEFAULT_DATABASE_ID;
  const lookup = readJson(lookupPath, 'lookup result');
  const report = fs.existsSync(reportPath) ? readJson(reportPath, 'fullflow report') : null;
  const video = normalizeVideo(lookup);
  const { pageTitle, blocks, quality } = buildPage(video, report);

  if (report?.targetBvid && report.targetBvid !== video.bvid) {
    console.warn(`WARN stale fullflow report target ${report.targetBvid}; publishing from current lookup ${video.bvid}.`);
  }

  if (args.dryRun || process.env.BILIBILI_NOTION_DRY_RUN === '1') {
    console.log(JSON.stringify({
      dryRun: true,
      databaseId,
      pageTitle,
      bvid: video.bvid,
      publishedDate: video.publishedDate,
      sections: ['视频核对', '今日摘要', '重点速览', '时间轴文本', '可跟进事项', '证据与产物', '转录说明'],
      quality
    }, null, 2));
    return;
  }

  const titleProperty = await findTitleProperty(databaseId);
  const existing = await findExistingPage(databaseId, titleProperty, pageTitle, video.bvid);
  if (existing) {
    await updatePageTitle(existing.id, titleProperty, pageTitle);
    const archived = await archiveChildren(existing.id);
    const appended = await appendChildren(existing.id, blocks);
    console.log(JSON.stringify({
      status: 'updated',
      pageTitle,
      pageId: existing.id,
      url: existing.url,
      archivedBlocks: archived,
      appendedBlocks: appended,
      quality
    }, null, 2));
    return;
  }

  const page = await createPage(databaseId, titleProperty, pageTitle, blocks);
  console.log(JSON.stringify({
    status: 'created',
    pageTitle,
    pageId: page.id,
    url: page.url,
    quality
  }, null, 2));
}

main().catch((error) => die(error.stack || error.message));
