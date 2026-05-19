#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const SEARCH_TYPES = new Set(["all", "answer", "article", "question"]);
const QUESTION_SORTS = new Set(["default", "created"]);

function parseArgs(argv) {
  const out = {
    mode: "search",
    cdpUrl: "http://127.0.0.1:9222",
    query: "",
    url: "",
    limit: 10,
    type: "all",
    sort: "default",
    maxContent: 4000,
    timeoutMs: 30000,
    outJson: "",
    outMarkdown: "",
    newTab: false,
  };

  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = () => {
      if (i + 1 >= argv.length) throw new Error(`Missing value for ${arg}`);
      i += 1;
      return argv[i];
    };
    if (arg === "--mode") out.mode = next();
    else if (arg === "--cdp-url") out.cdpUrl = next();
    else if (arg === "--query") out.query = next();
    else if (arg === "--url") out.url = next();
    else if (arg === "--limit") out.limit = Number.parseInt(next(), 10);
    else if (arg === "--type") out.type = next();
    else if (arg === "--sort") out.sort = next();
    else if (arg === "--max-content") out.maxContent = Number.parseInt(next(), 10);
    else if (arg === "--timeout-ms") out.timeoutMs = Number.parseInt(next(), 10);
    else if (arg === "--out-json") out.outJson = next();
    else if (arg === "--out-markdown") out.outMarkdown = next();
    else if (arg === "--new-tab") out.newTab = true;
    else if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  if (!Number.isFinite(out.limit) || out.limit < 1) out.limit = 10;
  if (!Number.isFinite(out.maxContent) || out.maxContent < 200) out.maxContent = 4000;
  if (!Number.isFinite(out.timeoutMs) || out.timeoutMs < 1000) out.timeoutMs = 30000;
  if (!SEARCH_TYPES.has(out.type)) out.type = "all";
  if (!QUESTION_SORTS.has(out.sort)) out.sort = "default";
  return out;
}

function printHelp() {
  console.log(`Usage:
  node zhihu_cdp.js --mode search --query "AI daily report" [--type all|answer|article|question] [--limit 10]
  node zhihu_cdp.js --mode question --url "https://www.zhihu.com/question/123456789" [--sort default|created]
  node zhihu_cdp.js --mode answer --url "https://www.zhihu.com/question/123456789/answer/987654321"
  node zhihu_cdp.js --mode article --url "https://zhuanlan.zhihu.com/p/123456789"
  node zhihu_cdp.js --mode fetch --url "https://www.zhihu.com/question/..."
  node zhihu_cdp.js --mode hot
  node zhihu_cdp.js --mode recommend
  node zhihu_cdp.js --mode observe

Options:
  --cdp-url URL         Chrome CDP URL, default http://127.0.0.1:9222
  --out-json PATH       Write structured JSON evidence
  --out-markdown PATH   Write compact Markdown evidence
  --new-tab             Open work in a new tab in the same logged-in profile
`);
}

function cleanText(value, max = 2000) {
  const text = String(value || "")
    .replace(/\u200b/g, "")
    .replace(/\s+/g, " ")
    .trim();
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

function decodeHtml(value) {
  return String(value || "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/p>/gi, "\n")
    .replace(/<\/div>/gi, "\n")
    .replace(/<\/h[1-6]>/gi, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

function stripHtml(value, max = 4000) {
  return cleanText(decodeHtml(value), max);
}

function ensureDir(filePath) {
  if (!filePath) return;
  fs.mkdirSync(path.dirname(path.resolve(filePath)), { recursive: true });
}

function toDateTime(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return "";
  const ms = n < 10_000_000_000 ? n * 1000 : n;
  return new Date(ms).toISOString();
}

function absolutize(href, base = "https://www.zhihu.com/") {
  try {
    return new URL(href, base).toString();
  } catch {
    return href || "";
  }
}

function toMarkdown(result) {
  const lines = [];
  lines.push(`# Zhihu ${result.mode}`);
  lines.push("");
  lines.push(`- URL: ${result.url || ""}`);
  lines.push(`- Captured: ${result.capturedAt}`);
  if (result.source) lines.push(`- Source: ${result.source}`);
  if (result.blocker) lines.push(`- Blocker: ${result.blocker}`);
  if (result.title) lines.push(`- Title: ${result.title}`);
  if (result.query) lines.push(`- Query: ${result.query}`);
  if (result.description) {
    lines.push("");
    lines.push(result.description);
  }
  lines.push("");

  for (const item of result.items || []) {
    lines.push(`## ${item.title || item.type || "Item"}`);
    if (item.url) lines.push(`- URL: ${item.url}`);
    if (item.type) lines.push(`- Type: ${item.type}`);
    if (item.author) lines.push(`- Author: ${item.author}`);
    if (item.votes != null && item.votes !== "") lines.push(`- Votes: ${item.votes}`);
    if (item.comments != null && item.comments !== "") lines.push(`- Comments: ${item.comments}`);
    if (item.heat) lines.push(`- Heat: ${item.heat}`);
    if (item.createdAt) lines.push(`- Created: ${item.createdAt}`);
    if (item.updatedAt) lines.push(`- Updated: ${item.updatedAt}`);
    if (item.meta) lines.push(`- Meta: ${item.meta}`);
    if (item.snippet) {
      lines.push("");
      lines.push(item.snippet);
    }
    lines.push("");
  }

  if (result.visibleText && (!result.items || result.items.length === 0)) {
    lines.push("## Visible Text");
    lines.push("");
    lines.push(result.visibleText);
  }
  return lines.join("\n");
}

async function getPage(browser, opts) {
  const context = browser.contexts()[0] || await browser.newContext();
  if (opts.newTab || context.pages().length === 0) return await context.newPage();
  return context.pages().find((p) => p.url().includes("zhihu.com")) || context.pages()[0];
}

async function waitSettled(page, timeoutMs) {
  await page.waitForLoadState("domcontentloaded", { timeout: timeoutMs }).catch(() => {});
  await page.waitForTimeout(1500);
}

async function detectBlocker(page) {
  const url = page.url();
  const body = cleanText(await page.locator("body").innerText({ timeout: 3000 }).catch(() => ""), 1200);
  const normalSignals = [
    "\u641c\u7d22",
    "\u5173\u6ce8",
    "\u63a8\u8350",
    "\u70ed\u699c",
    "\u6d88\u606f",
    "\u56de\u7b54",
    "\u8d5e\u540c",
  ];
  const blockerSignals = [
    "\u5b89\u5168\u9a8c\u8bc1",
    "\u9a8c\u8bc1\u7801",
    "\u8bf7\u5b8c\u6210\u9a8c\u8bc1",
    "\u767b\u5f55\u540e",
  ];
  const looksLikeNormalShell = normalSignals.some((signal) => body.includes(signal));
  const looksBlocked = blockerSignals.some((signal) => body.includes(signal));
  if (/signin|passport|captcha|verify/i.test(url) || (!looksLikeNormalShell && looksBlocked)) {
    return cleanText(body, 300) || "verification_required";
  }
  return "";
}

function pageTypeFromUrl(url) {
  if (/\/question\/\d+\/answer\/\d+/.test(url)) return "answer";
  if (/\/answer\/\d+/.test(url)) return "answer";
  if (/\/question\/\d+/.test(url)) return "question";
  if (/\/p\/\d+/.test(url)) return "article";
  if (/\/people\//.test(url)) return "user";
  if (/\/search/.test(url)) return "search";
  if (/\/hot/.test(url) || /\/billboard/.test(url)) return "hot";
  return "page";
}

function parseQuestionId(value) {
  const raw = String(value || "");
  const match = raw.match(/(?:question\/|^)(\d{3,})/);
  return match ? match[1] : "";
}

function parseAnswerTarget(value) {
  const raw = String(value || "");
  const typed = raw.match(/^answer:(\d+):(\d+)$/);
  if (typed) return { questionId: typed[1], answerId: typed[2] };
  const full = raw.match(/question\/(\d+)\/answer\/(\d+)/);
  if (full) return { questionId: full[1], answerId: full[2] };
  const answer = raw.match(/(?:answer\/|^)(\d{3,})/);
  if (answer) return { questionId: "", answerId: answer[1] };
  return { questionId: "", answerId: "" };
}

function parseArticleId(value) {
  const raw = String(value || "");
  const match = raw.match(/(?:zhuanlan\.zhihu\.com\/p\/|\/p\/|^)(\d{3,})/);
  return match ? match[1] : "";
}

function normalizeSearchNext(value) {
  if (typeof value !== "string" || !value) return "";
  try {
    const parsed = new URL(value);
    if (parsed.hostname === "api.zhihu.com" && parsed.pathname === "/search_v3") {
      return `https://www.zhihu.com/api/v4/search_v3${parsed.search}`;
    }
    if (parsed.hostname === "www.zhihu.com" && parsed.pathname === "/api/v4/search_v3") {
      return parsed.toString();
    }
  } catch {
    return "";
  }
  return "";
}

async function zhihuFetchJson(page, url) {
  return await page.evaluate(async (targetUrl) => {
    try {
      const response = await fetch(targetUrl, {
        credentials: "include",
        headers: {
          accept: "application/json, text/plain, */*",
          "x-requested-with": "fetch",
        },
      });
      const text = await response.text();
      if (!response.ok) return { ok: false, status: response.status, text: text.slice(0, 1000) };
      const safeText = text.replace(/("id"\s*:\s*)(\d{16,})/g, '$1"$2"');
      return { ok: true, status: response.status, data: JSON.parse(safeText) };
    } catch (error) {
      return { ok: false, status: 0, error: error && error.message ? error.message : String(error) };
    }
  }, url);
}

function searchItemUrl(obj) {
  const id = obj && obj.id != null ? String(obj.id) : "";
  if (!obj || !id) return "";
  if (obj.type === "answer") {
    const questionId = obj.question && obj.question.id != null ? String(obj.question.id) : "";
    return questionId ? `https://www.zhihu.com/question/${questionId}/answer/${id}` : `https://www.zhihu.com/answer/${id}`;
  }
  if (obj.type === "article") return `https://zhuanlan.zhihu.com/p/${id}`;
  if (obj.type === "question") return `https://www.zhihu.com/question/${id}`;
  return "";
}

function normalizeSearchItem(item) {
  if (!item || item.type !== "search_result" || !item.object) return null;
  const obj = item.object;
  if (!["answer", "article", "question"].includes(obj.type)) return null;
  const question = obj.question || {};
  const title = stripHtml(obj.title || question.name || question.title || "", 240);
  const url = searchItemUrl(obj);
  if (!title || !url) return null;
  return {
    type: obj.type,
    title,
    url,
    author: cleanText(obj.author && obj.author.name, 100),
    votes: obj.voteup_count || 0,
    comments: obj.comment_count || "",
    snippet: stripHtml(obj.excerpt || obj.content || obj.detail || "", 900),
    createdAt: toDateTime(obj.created_time),
    updatedAt: toDateTime(obj.updated_time),
  };
}

async function fetchSearchApi(page, opts) {
  const query = String(opts.query || "").trim();
  const pageSize = Math.min(Math.max(opts.limit, 1), 20);
  let url = `https://www.zhihu.com/api/v4/search_v3?q=${encodeURIComponent(query)}&t=general&offset=0&limit=${pageSize}`;
  const items = [];
  const seen = new Set();
  const visited = new Set();

  while (url && items.length < opts.limit && !visited.has(url)) {
    visited.add(url);
    const payload = await zhihuFetchJson(page, url);
    if (!payload.ok || !payload.data || !Array.isArray(payload.data.data)) {
      return { ok: false, status: payload.status, error: payload.error || payload.text || "search_api_failed", items };
    }
    for (const raw of payload.data.data) {
      if (opts.type !== "all" && raw && raw.object && raw.object.type !== opts.type) continue;
      const item = normalizeSearchItem(raw);
      if (!item || (opts.type !== "all" && item.type !== opts.type)) continue;
      const key = `${item.type}:${item.url}`;
      if (seen.has(key)) continue;
      seen.add(key);
      items.push(item);
      if (items.length >= opts.limit) break;
    }
    if (items.length >= opts.limit || payload.data.paging?.is_end) break;
    url = normalizeSearchNext(payload.data.paging && payload.data.paging.next);
  }

  return { ok: true, items };
}

async function fetchHotApi(page, limit) {
  const payload = await zhihuFetchJson(page, `https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=${Math.max(limit, 20)}`);
  if (!payload.ok || !payload.data || !Array.isArray(payload.data.data)) {
    return { ok: false, status: payload.status, error: payload.error || payload.text || "hot_api_failed", items: [] };
  }
  return {
    ok: true,
    items: payload.data.data.slice(0, limit).map((item, index) => {
      const target = item.target || {};
      const questionId = target.id == null ? "" : String(target.id);
      return {
        rank: index + 1,
        type: "question",
        title: cleanText(target.title, 240),
        url: questionId ? `https://www.zhihu.com/question/${questionId}` : "",
        heat: cleanText(item.detail_text, 100),
        votes: target.follower_count || "",
        comments: target.answer_count || "",
        snippet: cleanText(target.excerpt || target.detail || "", 800),
      };
    }).filter((item) => item.title && item.url),
  };
}

function feedTargetUrl(target) {
  const id = target && target.id != null ? String(target.id) : "";
  if (!target || !id) return "";
  if (target.type === "answer") {
    const questionId = target.question && target.question.id != null ? String(target.question.id) : "";
    return questionId ? `https://www.zhihu.com/question/${questionId}/answer/${id}` : `https://www.zhihu.com/answer/${id}`;
  }
  if (target.type === "article") return `https://zhuanlan.zhihu.com/p/${id}`;
  if (target.type === "question") return `https://www.zhihu.com/question/${id}`;
  return "";
}

async function fetchRecommendApi(page, limit) {
  let url = "https://www.zhihu.com/api/v3/feed/topstory/recommend?limit=10&desktop=true";
  const items = [];
  const seen = new Set();
  const visited = new Set();
  while (url && items.length < limit && !visited.has(url)) {
    visited.add(url);
    const payload = await zhihuFetchJson(page, url);
    if (!payload.ok || !payload.data || !Array.isArray(payload.data.data)) {
      return { ok: false, status: payload.status, error: payload.error || payload.text || "recommend_api_failed", items };
    }
    for (const row of payload.data.data) {
      const target = row.target || {};
      const url = feedTargetUrl(target);
      const title = cleanText(target.type === "answer" ? target.question && target.question.title : target.title || target.question && target.question.title, 240);
      if (!url || !title) continue;
      const key = `${target.type || ""}:${target.id || url}`;
      if (seen.has(key)) continue;
      seen.add(key);
      items.push({
        type: target.type || row.type || "feed",
        title,
        url,
        author: cleanText(target.author && target.author.name, 100),
        votes: target.voteup_count ?? (target.reaction && target.reaction.statistics && target.reaction.statistics.like_count) ?? "",
        comments: target.comment_count || "",
        snippet: stripHtml(target.excerpt || target.content || target.detail || "", 900),
      });
      if (items.length >= limit) break;
    }
    if (payload.data.paging?.is_end) break;
    url = typeof payload.data.paging?.next === "string" ? payload.data.paging.next : "";
  }
  return { ok: true, items };
}

function normalizeAnswerItem(answer, questionId = "", maxContent = 4000) {
  const id = answer && answer.id != null ? String(answer.id) : "";
  const qid = questionId || (answer.question && answer.question.id != null ? String(answer.question.id) : "");
  const title = cleanText((answer.question && (answer.question.title || answer.question.name)) || answer.title || "", 240);
  return {
    type: "answer",
    title,
    url: qid && id ? `https://www.zhihu.com/question/${qid}/answer/${id}` : id ? `https://www.zhihu.com/answer/${id}` : "",
    author: cleanText(answer.author && answer.author.name, 100),
    votes: answer.voteup_count || 0,
    comments: answer.comment_count || 0,
    createdAt: toDateTime(answer.created_time),
    updatedAt: toDateTime(answer.updated_time),
    snippet: stripHtml(answer.content || answer.excerpt || "", maxContent),
  };
}

async function fetchQuestionApi(page, questionId, opts) {
  const include = "data[*].content,voteup_count,comment_count,author,created_time,updated_time";
  const url = `https://www.zhihu.com/api/v4/questions/${questionId}/answers?limit=${Math.min(Math.max(opts.limit, 1), 20)}&offset=0&sort_by=${encodeURIComponent(opts.sort)}&include=${encodeURIComponent(include)}`;
  const payload = await zhihuFetchJson(page, url);
  if (!payload.ok || !payload.data || !Array.isArray(payload.data.data)) {
    return { ok: false, status: payload.status, error: payload.error || payload.text || "question_api_failed", items: [] };
  }
  const title = await page.locator("h1.QuestionHeader-title, h1").first().innerText({ timeout: 2500 }).catch(() => "");
  const description = await page.locator(".QuestionRichText, .QuestionHeader-detail").first().innerText({ timeout: 2500 }).catch(() => "");
  return {
    ok: true,
    title: cleanText(title, 240),
    description: cleanText(description, 1200),
    items: payload.data.data.slice(0, opts.limit).map((answer) => normalizeAnswerItem(answer, questionId, opts.maxContent)).filter((item) => item.url),
  };
}

async function fetchAnswerApi(page, answerId, opts) {
  const include = "content,voteup_count,comment_count,author,created_time,updated_time,question";
  const payload = await zhihuFetchJson(page, `https://www.zhihu.com/api/v4/answers/${answerId}?include=${encodeURIComponent(include)}`);
  if (!payload.ok || !payload.data || !payload.data.id) {
    return { ok: false, status: payload.status, error: payload.error || payload.text || "answer_api_failed", items: [] };
  }
  const item = normalizeAnswerItem(payload.data, "", opts.maxContent);
  return {
    ok: true,
    title: item.title,
    description: "",
    items: [item],
  };
}

async function extractSearchDom(page, limit) {
  return await page.evaluate((maxItems) => {
    const clean = (v, max = 700) => {
      const text = String(v || "").replace(/\u200b/g, "").replace(/\s+/g, " ").trim();
      return text.length > max ? `${text.slice(0, max)}...` : text;
    };
    const absolutize = (href) => {
      try {
        return new URL(href, location.href).toString();
      } catch {
        return href || "";
      }
    };
    const isSignalUrl = (url) => /\/question\/\d+|\/answer\/\d+|\/p\/\d+|\/people\//.test(url);
    const navTitles = new Set([
      "\u7efc\u5408",
      "\u7528\u6237",
      "\u4e13\u680f",
      "\u5708\u5b50",
      "\u8bdd\u9898",
      "\u89c6\u9891",
      "\u767b\u5f55/\u6ce8\u518c",
    ]);
    const cards = Array.from(document.querySelectorAll(".SearchResult-Card, .Card, [data-za-detail-view-path-module]"));
    const seen = new Set();
    const items = [];

    for (const card of cards) {
      const anchors = Array.from(card.querySelectorAll("a[href]"));
      const primary = anchors.find((a) => /\/question\/|\/answer\/|\/p\/|\/zvideo\/|\/people\//.test(a.getAttribute("href") || "")) || anchors[0];
      if (!primary) continue;
      const url = absolutize(primary.getAttribute("href"));
      if (!url || seen.has(url)) continue;
      seen.add(url);
      const titleNode = card.querySelector("h2, h3, .ContentItem-title, .QuestionItem-title, a[data-za-detail-view-element_name]");
      const title = clean(titleNode ? titleNode.textContent : primary.textContent, 180);
      if (!isSignalUrl(url) || navTitles.has(title)) continue;
      const authorNode = card.querySelector(".AuthorInfo-name, .UserLink-link, [class*=AuthorInfo] a");
      const metaNode = card.querySelector(".ContentItem-status, .SearchItem-meta, .QuestionItem-meta, .RichContent-actions");
      const contentNode = card.querySelector(".RichContent-inner, .RichContent, .SearchResult-Card .Highlight, .ContentItem-excerpt");
      items.push({
        type: url.includes("/answer/") ? "answer" : url.includes("/question/") ? "question" : url.includes("/p/") ? "article" : url.includes("/people/") ? "user" : "result",
        title,
        url,
        author: clean(authorNode && authorNode.textContent, 80),
        meta: clean(metaNode && metaNode.textContent, 160),
        snippet: clean(contentNode ? contentNode.textContent : card.textContent, 700),
      });
      if (items.length >= maxItems) break;
    }

    if (items.length < maxItems) {
      for (const a of Array.from(document.querySelectorAll('a[href*="/question/"], a[href*="/answer/"], a[href*="/p/"], a[href*="/people/"]'))) {
        const url = absolutize(a.getAttribute("href"));
        if (!url || seen.has(url) || !isSignalUrl(url)) continue;
        seen.add(url);
        items.push({
          type: url.includes("/answer/") ? "answer" : url.includes("/question/") ? "question" : url.includes("/p/") ? "article" : "user",
          title: clean(a.textContent, 180),
          url,
          author: "",
          meta: "",
          snippet: clean(a.closest(".Card, .List-item, .SearchResult-Card, div")?.textContent || "", 500),
        });
        if (items.length >= maxItems) break;
      }
    }
    return items;
  }, limit);
}

async function extractArticleDom(page, maxContent) {
  return await page.evaluate((contentLimit) => {
    const clean = (v, max = 3000) => {
      const text = String(v || "").replace(/\u200b/g, "").replace(/\s+/g, " ").trim();
      return text.length > max ? `${text.slice(0, max)}...` : text;
    };
    const title = clean(document.querySelector(".Post-Title, h1.ContentItem-title, .ArticleTitle, h1")?.textContent, 240);
    const author = clean(document.querySelector(".AuthorInfo-name, .UserLink-link")?.textContent, 100);
    const publishTime = clean(document.querySelector(".ContentItem-time, .Post-Time")?.textContent, 120);
    const contentEl = document.querySelector(".Post-RichTextContainer, .RichText, .ArticleContent, article");
    const snippet = clean(contentEl ? contentEl.textContent : document.body?.innerText, contentLimit);
    const imageUrls = [];
    if (contentEl) {
      for (const img of Array.from(contentEl.querySelectorAll("img"))) {
        const src = img.getAttribute("data-original") || img.getAttribute("data-actualsrc") || img.src;
        if (src && !src.includes("data:image")) imageUrls.push(src);
      }
    }
    return { title, author, publishTime, snippet, imageUrls };
  }, maxContent);
}

async function extractFetchDom(page, limit, maxContent) {
  return await page.evaluate((args) => {
    const clean = (v, max = 3000) => {
      const text = String(v || "").replace(/\u200b/g, "").replace(/\s+/g, " ").trim();
      return text.length > max ? `${text.slice(0, max)}...` : text;
    };
    const abs = (href) => {
      try {
        return new URL(href, location.href).toString();
      } catch {
        return href || "";
      }
    };
    const titleNode = document.querySelector("h1.QuestionHeader-title, h1.Post-Title, h1, title");
    const detailNode = document.querySelector(".QuestionRichText, .QuestionHeader-detail, .Post-RichTextContainer, article");
    const cards = Array.from(document.querySelectorAll(".List-item, .AnswerCard, .ContentItem, .Card")).slice(0, args.limit);
    const items = [];

    for (const card of cards) {
      const link = card.querySelector('a[href*="/answer/"], a[href*="/question/"], a[href*="/p/"], a[href]');
      const authorNode = card.querySelector(".AuthorInfo-name, .UserLink-link, [class*=AuthorInfo] a");
      const title = clean(card.querySelector(".ContentItem-title, h2, h3")?.textContent || link?.textContent || "", 180);
      const content = card.querySelector(".RichContent-inner, .RichText, .ContentItem-excerpt, .RichContent") || card;
      const meta = card.querySelector(".ContentItem-status, .VoteButton, .RichContent-actions");
      const text = clean(content.textContent, args.maxContent);
      if (!text || items.some((item) => item.snippet === text)) continue;
      items.push({
        type: "content",
        title,
        url: link ? abs(link.getAttribute("href")) : location.href,
        author: clean(authorNode && authorNode.textContent, 80),
        meta: clean(meta && meta.textContent, 180),
        snippet: text,
      });
    }

    return {
      title: clean(titleNode && titleNode.textContent, 240),
      description: clean(detailNode && detailNode.textContent, 1800),
      items,
      visibleText: clean(document.body ? document.body.innerText : "", 6000),
    };
  }, { limit, maxContent });
}

async function navigateForMode(page, opts) {
  if (opts.mode === "search") {
    if (!opts.query) throw new Error("--query is required for search mode");
    await page.goto(`https://www.zhihu.com/search?type=content&q=${encodeURIComponent(opts.query)}`, { waitUntil: "domcontentloaded", timeout: opts.timeoutMs });
  } else if (opts.mode === "question") {
    const questionId = parseQuestionId(opts.url || opts.query);
    if (!questionId) throw new Error("--url or --query must include a Zhihu question id");
    await page.goto(`https://www.zhihu.com/question/${questionId}`, { waitUntil: "domcontentloaded", timeout: opts.timeoutMs });
  } else if (opts.mode === "answer") {
    const target = parseAnswerTarget(opts.url || opts.query);
    if (!target.answerId) throw new Error("--url or --query must include a Zhihu answer id");
    const navUrl = target.questionId ? `https://www.zhihu.com/question/${target.questionId}/answer/${target.answerId}` : `https://www.zhihu.com/answer/${target.answerId}`;
    await page.goto(navUrl, { waitUntil: "domcontentloaded", timeout: opts.timeoutMs });
  } else if (opts.mode === "article") {
    const articleId = parseArticleId(opts.url || opts.query);
    if (!articleId) throw new Error("--url or --query must include a Zhihu article id");
    await page.goto(`https://zhuanlan.zhihu.com/p/${articleId}`, { waitUntil: "domcontentloaded", timeout: opts.timeoutMs });
  } else if (opts.mode === "fetch") {
    if (!opts.url) throw new Error("--url is required for fetch mode");
    await page.goto(opts.url, { waitUntil: "domcontentloaded", timeout: opts.timeoutMs });
  } else if (opts.mode === "hot") {
    await page.goto(opts.url || "https://www.zhihu.com/hot", { waitUntil: "domcontentloaded", timeout: opts.timeoutMs });
  } else if (opts.mode === "recommend") {
    await page.goto(opts.url || "https://www.zhihu.com", { waitUntil: "domcontentloaded", timeout: opts.timeoutMs });
  } else if (opts.mode === "observe") {
    if (opts.url) await page.goto(opts.url, { waitUntil: "domcontentloaded", timeout: opts.timeoutMs });
  } else {
    throw new Error(`Unsupported mode: ${opts.mode}`);
  }
}

async function buildResult(page, opts, blocker) {
  const currentUrl = page.url();
  const base = {
    mode: opts.mode,
    query: opts.query || "",
    url: currentUrl,
    pageType: pageTypeFromUrl(currentUrl),
    capturedAt: new Date().toISOString(),
    blocker,
  };
  if (blocker) return { ...base, source: "blocked", title: await page.title(), items: [] };

  if (opts.mode === "search") {
    const api = await fetchSearchApi(page, opts);
    const items = api.ok && api.items.length > 0 ? api.items : await extractSearchDom(page, opts.limit);
    return { ...base, source: api.ok && api.items.length > 0 ? "zhihu_api" : "dom_fallback", title: await page.title(), items };
  }

  if (opts.mode === "hot") {
    const api = await fetchHotApi(page, opts.limit);
    const items = api.ok && api.items.length > 0 ? api.items : await extractSearchDom(page, opts.limit);
    return { ...base, source: api.ok && api.items.length > 0 ? "zhihu_api" : "dom_fallback", title: await page.title(), items };
  }

  if (opts.mode === "recommend") {
    const api = await fetchRecommendApi(page, opts.limit);
    const items = api.ok && api.items.length > 0 ? api.items : await extractSearchDom(page, opts.limit);
    return { ...base, source: api.ok && api.items.length > 0 ? "zhihu_api" : "dom_fallback", title: await page.title(), items };
  }

  if (opts.mode === "question") {
    const questionId = parseQuestionId(currentUrl || opts.url || opts.query);
    const api = questionId ? await fetchQuestionApi(page, questionId, opts) : { ok: false, items: [] };
    if (api.ok) return { ...base, source: "zhihu_api", title: api.title || await page.title(), description: api.description || "", items: api.items };
  }

  if (opts.mode === "answer") {
    const target = parseAnswerTarget(currentUrl || opts.url || opts.query);
    const api = target.answerId ? await fetchAnswerApi(page, target.answerId, opts) : { ok: false, items: [] };
    if (api.ok) return { ...base, source: "zhihu_api", title: api.title || await page.title(), description: api.description || "", items: api.items };
  }

  if (opts.mode === "article") {
    const article = await extractArticleDom(page, opts.maxContent);
    return {
      ...base,
      source: "dom_article",
      title: article.title || await page.title(),
      items: [{
        type: "article",
        title: article.title || await page.title(),
        url: currentUrl,
        author: article.author,
        meta: article.publishTime,
        snippet: article.snippet,
        imageUrls: article.imageUrls,
      }],
    };
  }

  if (opts.mode === "fetch") {
    const type = pageTypeFromUrl(currentUrl);
    if (type === "question") {
      const questionId = parseQuestionId(currentUrl);
      const api = questionId ? await fetchQuestionApi(page, questionId, opts) : { ok: false, items: [] };
      if (api.ok) return { ...base, source: "zhihu_api", title: api.title || await page.title(), description: api.description || "", items: api.items };
    }
    if (type === "answer") {
      const target = parseAnswerTarget(currentUrl);
      const api = target.answerId ? await fetchAnswerApi(page, target.answerId, opts) : { ok: false, items: [] };
      if (api.ok) return { ...base, source: "zhihu_api", title: api.title || await page.title(), description: api.description || "", items: api.items };
    }
    if (type === "article") {
      const article = await extractArticleDom(page, opts.maxContent);
      return {
        ...base,
        source: "dom_article",
        title: article.title || await page.title(),
        items: [{
          type: "article",
          title: article.title || await page.title(),
          url: currentUrl,
          author: article.author,
          meta: article.publishTime,
          snippet: article.snippet,
          imageUrls: article.imageUrls,
        }],
      };
    }
    const extracted = await extractFetchDom(page, opts.limit, opts.maxContent);
    return { ...base, source: "dom_fallback", ...extracted };
  }

  const extracted = await extractFetchDom(page, opts.limit, opts.maxContent);
  return { ...base, source: "dom_observe", ...extracted };
}

async function main() {
  const opts = parseArgs(process.argv);
  const browser = await chromium.connectOverCDP(opts.cdpUrl, { timeout: opts.timeoutMs });
  const page = await getPage(browser, opts);

  try {
    await navigateForMode(page, opts);
    await waitSettled(page, opts.timeoutMs);
    const blocker = await detectBlocker(page);
    const result = await buildResult(page, opts, blocker);

    const json = JSON.stringify(result, null, 2);
    if (opts.outJson) {
      ensureDir(opts.outJson);
      fs.writeFileSync(opts.outJson, json, "utf8");
    }
    if (opts.outMarkdown) {
      ensureDir(opts.outMarkdown);
      fs.writeFileSync(opts.outMarkdown, toMarkdown(result), "utf8");
    }
    console.log(json);
  } finally {
    await browser.close().catch(() => {});
  }
}

main().catch((error) => {
  console.error(JSON.stringify({ ok: false, error: error.message, stack: error.stack }, null, 2));
  process.exit(1);
});
