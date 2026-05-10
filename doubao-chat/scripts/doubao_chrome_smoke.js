#!/usr/bin/env node
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

function arg(name, fallback = "") {
  const prefix = `--${name}=`;
  const inline = process.argv.find((item) => item.startsWith(prefix));
  if (inline) return inline.slice(prefix.length);
  const index = process.argv.indexOf(`--${name}`);
  if (index >= 0 && index + 1 < process.argv.length) return process.argv[index + 1];
  return fallback;
}

function writeFile(filePath, value) {
  if (!filePath) return "";
  fs.mkdirSync(path.dirname(path.resolve(filePath)), { recursive: true });
  fs.writeFileSync(filePath, value, "utf8");
  return filePath;
}

async function visibleLocator(page, selectors, timeout) {
  for (const selector of selectors) {
    const locator = page.locator(selector).last();
    const count = await locator.count().catch(() => 0);
    if (!count) continue;
    if (await locator.isVisible({ timeout: Math.min(timeout, 5000) }).catch(() => false)) {
      return locator;
    }
  }
  return null;
}

async function getBodyText(page) {
  return page.locator("body").innerText({ timeout: 10000 }).catch(() => "");
}

function extractReply(bodyText, prompt) {
  const noise = new Set([
    "豆包",
    "新对话",
    "AI 创作",
    "更多",
    "历史对话",
    "关于豆包",
    "内容由豆包 AI 生成，请仔细甄别",
    "下载电脑版",
    "登录",
    "快速",
    "新",
    "PPT 生成",
    "图像生成",
    "帮我写作",
    "翻译",
    "编程",
    "下载豆包电脑版，体验更强大的 AI 能力",
  ]);
  const lines = bodyText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const promptIndex = lines.lastIndexOf(prompt.trim());
  const candidates = (promptIndex >= 0 ? lines.slice(promptIndex + 1) : lines)
    .filter((line) => !noise.has(line))
    .filter((line) => line !== prompt.trim())
    .filter((line) => !line.endsWith("?") && !line.endsWith("？"));
  return candidates[0] || "";
}

async function waitForStableReply(page, prompt, timeout) {
  const deadline = Date.now() + timeout;
  let previous = "";
  let stableCount = 0;
  let lastText = "";

  while (Date.now() < deadline) {
    const text = await getBodyText(page);
    lastText = text;
    const hasPrompt = text.includes(prompt);
    const stillLoading = /正在生成|停止生成|思考中/.test(text);

    if (hasPrompt && text === previous && !stillLoading) {
      stableCount += 1;
      if (stableCount >= 2) {
        return { bodyText: text, reply: extractReply(text, prompt), stable: true };
      }
    } else {
      stableCount = 0;
    }

    previous = text;
    await page.waitForTimeout(1500);
  }

  return { bodyText: lastText, reply: extractReply(lastText, prompt), stable: false };
}

async function main() {
  const cdpUrl = arg("cdp-url", process.env.DOUBAO_CDP_URL || "http://127.0.0.1:9222");
  const doubaoUrl = arg("url", "https://www.doubao.com/chat/");
  const prompt = arg("prompt", "请只回复：技能测试成功");
  const timeout = Number(arg("timeout-ms", "60000"));
  const screenshot = arg("screenshot");
  const textOut = arg("text-out");

  const browser = await chromium.connectOverCDP(cdpUrl, { timeout });
  try {
    const context = browser.contexts()[0] || await browser.newContext();
    let page = context.pages().find((candidate) => candidate.url().includes("doubao.com/chat"));
    if (!page) page = await context.newPage();

    if (!page.url().includes("doubao.com/chat")) {
      await page.goto(doubaoUrl, { waitUntil: "domcontentloaded", timeout });
    }

    const input = await visibleLocator(
      page,
      [
        "textarea[placeholder*='发消息']",
        "textarea",
        "[contenteditable='true']",
        "[role='textbox']",
      ],
      timeout,
    );
    if (!input) throw new Error("Could not find Doubao chat input. Login or UI verification may be required.");

    await input.click({ timeout });
    await input.fill(prompt, { timeout }).catch(async () => {
      await input.press(process.platform === "darwin" ? "Meta+A" : "Control+A", { timeout: 5000 }).catch(() => {});
      await input.type(prompt, { delay: 5, timeout });
    });
    await input.press("Enter", { timeout: 10000 });

    const result = await waitForStableReply(page, prompt, timeout);
    const screenshotPath = screenshot ? (fs.mkdirSync(path.dirname(path.resolve(screenshot)), { recursive: true }), await page.screenshot({ path: screenshot, fullPage: true }), screenshot) : "";
    const textPath = writeFile(textOut, result.bodyText);

    console.log(JSON.stringify({
      ok: Boolean(result.reply),
      url: page.url(),
      title: await page.title(),
      stable: result.stable,
      prompt,
      reply: result.reply,
      evidence: {
        screenshot: screenshotPath,
        text: textPath,
      },
    }, null, 2));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(JSON.stringify({
    ok: false,
    error: error.message,
    stack: error.stack,
  }, null, 2));
  process.exit(1);
});
