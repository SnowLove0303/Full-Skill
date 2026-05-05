import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const NOTION_VERSION = process.env.NOTION_VERSION || "2022-06-28";
const DATABASE_ID =
  process.env.BILIBILI_DAILY_NOTION_DATABASE_ID || "34d003b6-8bec-8027-a6ea-fd8b918c72c5";
const WORKSPACE =
  process.env.OPENCLAW_AGENT_WORKSPACE ||
  process.env.BILIBILI_SKILL_WORKSPACE ||
  process.cwd();
const LOOKUP_RESULT =
  process.env.JUYA_LOOKUP_RESULT || path.join(WORKSPACE, "juya-today-daily-result.json");
const FULLFLOW_REPORT =
  process.env.JUYA_FULLFLOW_REPORT || path.join(WORKSPACE, "juya-today-fullflow-report.json");
const TARGET_PAGE_ID = process.env.BILIBILI_DAILY_NOTION_PAGE_ID || "";

function fail(code, message, detail = {}) {
  console.log(`${code}: ${message}`);
  if (Object.keys(detail).length) console.log(JSON.stringify(detail, null, 2));
  process.exit(1);
}

function decodeText(buffer) {
  if (buffer.length >= 2 && buffer[0] === 0xff && buffer[1] === 0xfe) {
    return buffer.subarray(2).toString("utf16le");
  }
  return buffer.toString("utf8");
}

function readTextIfExists(file) {
  return fs.existsSync(file) ? decodeText(fs.readFileSync(file)).replace(/^\uFEFF/, "") : "";
}

function readJson(file) {
  if (!fs.existsSync(file)) fail("FULLFLOW_NOTION_BLOCKED", `Missing file: ${file}`);
  return JSON.parse(readTextIfExists(file));
}

function getToken() {
  const candidates = [
    process.env.NOTION_KEY,
    process.env.NOTION_TOKEN,
    process.env.NOTION_API_KEY,
    readTextIfExists(path.join(WORKSPACE, ".config", "notion", "api_key")).trim(),
    readTextIfExists(path.join(os.homedir(), ".config", "notion", "api_key")).trim(),
  ];
  const token = candidates.find(Boolean);
  if (!token) fail("FULLFLOW_NOTION_BLOCKED", "Missing Notion API token.");
  return token;
}

function rt(text) {
  return [{ type: "text", text: { content: String(text ?? "").slice(0, 2000) } }];
}

function paragraph(text) {
  return { object: "block", type: "paragraph", paragraph: { rich_text: rt(text) } };
}

function h2(text) {
  return { object: "block", type: "heading_2", heading_2: { rich_text: rt(text) } };
}

function bullet(text) {
  return { object: "block", type: "bulleted_list_item", bulleted_list_item: { rich_text: rt(text) } };
}

function codeBlock(text, language = "plain text") {
  return {
    object: "block",
    type: "code",
    code: { language, rich_text: rt(String(text ?? "").slice(0, 1800)) },
  };
}

async function notionRequest(method, endpoint, token, body) {
  const response = await fetch(`https://api.notion.com/v1${endpoint}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      "Notion-Version": NOTION_VERSION,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    fail("FULLFLOW_NOTION_BLOCKED", `Notion API ${method} ${endpoint} failed with ${response.status}.`, {
      notionError: data?.message || data?.code || "unknown",
    });
  }
  return data;
}

async function getTitleProperty(token) {
  const db = await notionRequest("GET", `/databases/${DATABASE_ID}`, token);
  const entry = Object.entries(db.properties || {}).find(([, prop]) => prop?.type === "title");
  if (!entry) fail("FULLFLOW_NOTION_BLOCKED", "Target Notion database has no title property.");
  return entry[0];
}

async function createDailyPage(token, titleProperty, pageTitle) {
  if (TARGET_PAGE_ID) {
    await notionRequest("PATCH", `/pages/${TARGET_PAGE_ID}`, token, {
      properties: {
        [titleProperty]: { title: rt(pageTitle) },
      },
    });
    return { id: TARGET_PAGE_ID, url: `https://www.notion.so/${TARGET_PAGE_ID.replace(/-/g, "")}` };
  }

  return notionRequest("POST", "/pages", token, {
    parent: { database_id: DATABASE_ID },
    properties: {
      [titleProperty]: { title: rt(pageTitle) },
    },
  });
}

async function appendBlocks(token, pageId, blocks) {
  for (let i = 0; i < blocks.length; i += 90) {
    await notionRequest("PATCH", `/blocks/${pageId}/children`, token, {
      children: blocks.slice(i, i + 90),
    });
  }
}

function pickArtifact(items = [], suffixOrPattern) {
  return (items || []).find((item) => suffixOrPattern.test(String(item.FullName || item.fullName || ""))) || {};
}

function loadTranscript(report) {
  const transcript = pickArtifact(report.downloadArtifacts, /_transcript\.txt$/i);
  const file = transcript.FullName || "";
  if (!file || !fs.existsSync(file)) return "";
  return readTextIfExists(file).replace(/\r/g, "").replace(/\n{3,}/g, "\n\n").trim();
}

function loadNote(report) {
  const note = pickArtifact(report.noteArtifacts, /\.md$/i);
  const file = note.FullName || "";
  if (!file || !fs.existsSync(file)) return "";
  return readTextIfExists(file).trim();
}

function makeBlocks({ lookup, report, transcript, note }) {
  const video = lookup.result || report.lookup || {};
  const steps = report.steps || [];
  const failed = steps.filter((step) => Number(step.exitCode) !== 0);
  const artifacts = [
    ...(report.downloadArtifacts || []).map((item) => item.FullName).filter(Boolean),
    ...(report.noteArtifacts || []).map((item) => item.FullName).filter(Boolean),
  ];

  const blocks = [
    h2("1. 视频来源校验"),
    bullet(`UP: ${video.author || "unknown"} / MID: ${video.mid || "unknown"}`),
    bullet(`标题: ${video.title || "unknown"}`),
    bullet(`BVID: ${video.bvid || report.targetBvid || "unknown"}`),
    bullet(`发布日期: ${video.published_at || video.published_date || "unknown"}`),
    bullet(`链接: ${video.url || (video.bvid ? `https://www.bilibili.com/video/${video.bvid}` : "unknown")}`),
    bullet(`选择规则: ${lookup.selection_rule || "strict Juya daily validation"}`),
    h2("2. 执行结果"),
    bullet(`整体状态: ${report.success ? "成功" : "失败"}`),
    bullet(`输出目录: ${report.outputDir || ""}`),
    bullet(`笔记目录: ${report.vaultDir || ""}`),
    bullet(`报告文件: ${FULLFLOW_REPORT}`),
    h2("3. 步骤明细"),
    ...steps.map((step) => bullet(`${step.name}: exitCode=${step.exitCode}`)),
  ];

  if (failed.length) {
    blocks.push(h2("4. 失败输出"));
    for (const step of failed) {
      blocks.push(codeBlock(`${step.name}\n${(step.output || []).slice(-30).join("\n")}`));
    }
  }

  if (artifacts.length) {
    blocks.push(h2("4. 产物路径"));
    for (const item of artifacts.slice(0, 20)) blocks.push(bullet(item));
  }

  if (note) {
    blocks.push(h2("5. 生成笔记摘录"));
    blocks.push(codeBlock(note.slice(0, 1800), "markdown"));
  }

  if (transcript) {
    blocks.push(h2("6. 转录摘录"));
    blocks.push(paragraph(transcript.slice(0, 1800)));
  }

  return blocks;
}

const token = getToken();
const lookup = readJson(LOOKUP_RESULT);
const report = readJson(FULLFLOW_REPORT);
const video = lookup.result || report.lookup || {};
const date = lookup.target_date || video.published_date || new Date().toISOString().slice(0, 10);
const bvid = video.bvid || report.targetBvid || "unknown";
const title = `Juya AI ${date} ${bvid}`;
const titleProperty = await getTitleProperty(token);
const page = await createDailyPage(token, titleProperty, title);
await appendBlocks(token, page.id, makeBlocks({
  lookup,
  report,
  transcript: loadTranscript(report),
  note: loadNote(report),
}));

console.log("FULLFLOW_NOTION_OK");
console.log(`PAGE_ID=${page.id}`);
console.log(`PAGE_URL=${page.url}`);
