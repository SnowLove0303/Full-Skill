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

function argValues(name) {
  const prefix = `--${name}=`;
  const values = [];
  for (let index = 0; index < process.argv.length; index += 1) {
    const item = process.argv[index];
    if (item.startsWith(prefix)) {
      values.push(item.slice(prefix.length));
    } else if (item === `--${name}` && index + 1 < process.argv.length) {
      values.push(process.argv[index + 1]);
      index += 1;
    }
  }
  return values;
}

function numberArg(name, fallback) {
  const value = Number(arg(name, String(fallback)));
  return Number.isFinite(value) && value >= 0 ? value : fallback;
}

function writeFile(filePath, value) {
  if (!filePath) return "";
  fs.mkdirSync(path.dirname(path.resolve(filePath)), { recursive: true });
  fs.writeFileSync(filePath, value, "utf8");
  return filePath;
}

function writeJson(filePath, value) {
  if (!filePath) return "";
  fs.mkdirSync(path.dirname(path.resolve(filePath)), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  return filePath;
}

function runtimePath(name) {
  const dir = path.join(__dirname, ".runtime");
  fs.mkdirSync(dir, { recursive: true });
  return path.join(dir, name);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function acquireSendLock(timeoutMs) {
  const lockDir = runtimePath("doubao-send.lock");
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      fs.mkdirSync(lockDir);
      fs.writeFileSync(path.join(lockDir, "owner.json"), JSON.stringify({
        pid: process.pid,
        startedAt: new Date().toISOString(),
      }, null, 2));
      return () => fs.rmSync(lockDir, { recursive: true, force: true });
    } catch (error) {
      const stat = fs.statSync(lockDir, { throwIfNoEntry: false });
      if (stat && Date.now() - stat.mtimeMs > Math.max(120000, timeoutMs * 2)) {
        fs.rmSync(lockDir, { recursive: true, force: true });
        continue;
      }
      await sleep(500);
    }
  }
  throw new Error("Timed out waiting for Doubao send lock. Another agent may still be using the browser.");
}

async function applyCooldown(cooldownMs) {
  if (!cooldownMs) return 0;
  const filePath = runtimePath("last-send.json");
  const raw = fs.existsSync(filePath) ? fs.readFileSync(filePath, "utf8") : "";
  let lastSentAt = 0;
  try {
    lastSentAt = raw ? Number(JSON.parse(raw).lastSentAt || 0) : 0;
  } catch {
    lastSentAt = 0;
  }
  const waitMs = Math.max(0, lastSentAt + cooldownMs - Date.now());
  if (waitMs > 0) await sleep(waitMs);
  return waitMs;
}

function recordSendTimestamp() {
  fs.writeFileSync(runtimePath("last-send.json"), JSON.stringify({
    lastSentAt: Date.now(),
    iso: new Date().toISOString(),
  }, null, 2));
}

async function visibleLocator(page, selectors, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    for (const selector of selectors) {
      const locator = page.locator(selector).last();
      const count = await locator.count().catch(() => 0);
      if (!count) continue;
      if (await locator.isVisible().catch(() => false)) {
        return locator;
      }
    }
    await page.waitForTimeout(500);
  }
  return null;
}

async function getBodyText(page) {
  return page.locator("body").innerText({ timeout: 10000 }).catch(() => "");
}

function detectHumanGate(bodyText, pageUrl = "") {
  const text = bodyText.toLowerCase();
  const url = pageUrl.toLowerCase();
  const checks = [
    ["login", /\blog\s*in\b|sign\s*in|\u626b\u7801\u767b\u5f55|\u624b\u673a\u53f7\u767b\u5f55|\u8bf7\u5148\u767b\u5f55|\u7acb\u5373\u767b\u5f55|\u5feb\u6377\u767b\u5f55/],
    ["captcha", /captcha|\u8bf7\u8f93\u5165\u9a8c\u8bc1\u7801|\u83b7\u53d6\u9a8c\u8bc1\u7801|\u8bf7\u5b8c\u6210\u9a8c\u8bc1|\u62d6\u52a8\u6ed1\u5757|\u6ed1\u5757\u9a8c\u8bc1|\u5b89\u5168\u9a8c\u8bc1/],
    ["risk-control", /risk|unusual traffic|\u98ce\u9669|\u8d26\u53f7\u5b89\u5168|\u73af\u5883\u5f02\u5e38|\u64cd\u4f5c\u9891\u7e41|\u8bf7\u7a0d\u540e\u518d\u8bd5/],
    ["phone-or-app-check", /phone verification|app confirmation|\u624b\u673a\u9a8c\u8bc1|\u77ed\u4fe1\u9a8c\u8bc1|\u8bf7\u5728.*app.*\u786e\u8ba4/],
  ];
  const hit = checks.find(([, pattern]) => pattern.test(text) || pattern.test(url));
  return hit ? hit[0] : "";
}

async function assertNoHumanGate(page, stage) {
  const bodyText = await getBodyText(page);
  const blocker = detectHumanGate(bodyText, page.url());
  if (blocker) {
    const error = new Error(`Doubao ${blocker} blocker detected during ${stage}. Stop automation and ask the user to resolve the browser verification manually.`);
    error.blocker = blocker;
    throw error;
  }
  return bodyText;
}

function normalizeLines(text) {
  return text
    .replace(/\u00a0/g, " ")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function isNoiseLine(line) {
  const lower = line.toLowerCase();
  if (line.length > 3000) return true;
  const exactNoise = [
    "doubao",
    "new chat",
    "history",
    "login",
    "download",
    "send",
    "stop generating",
    "regenerate",
    "\u8c46\u5305",
    "\u65b0\u5bf9\u8bdd",
    "\u5386\u53f2\u5bf9\u8bdd",
    "\u767b\u5f55",
    "\u4e0b\u8f7d",
    "\u53d1\u9001",
    "\u505c\u6b62\u751f\u6210",
    "\u91cd\u65b0\u751f\u6210",
    "\u66f4\u591a",
    "\u5feb\u901f",
    "\u56fe\u50cf\u751f\u6210",
    "\u6570\u636e\u5206\u6790",
    "\u5e2e\u6211\u5199\u4f5c",
    "\u7f16\u7a0b",
    "\u97f3\u4e50\u751f\u6210",
    "\u7ffb\u8bd1",
    "\u89c6\u9891\u751f\u6210",
    "\u8bb0\u5f55\u4f1a\u8bae",
    "\u6df1\u5165\u7814\u7a76",
    "ai \u64ad\u5ba2",
    "\u89e3\u9898\u7b54\u7591",
    "ppt \u751f\u6210",
    "\u8d85\u80fd\u6a21\u5f0f",
  ];
  const containsNoise = [
    "\u5185\u5bb9\u7531\u8c46\u5305ai\u751f\u6210",
  ];

  return exactNoise.some((noise) => lower === noise.toLowerCase())
    || containsNoise.some((noise) => lower.includes(noise.toLowerCase()));
}

function looksLikeFollowupSuggestion(line) {
  return /[?\uFF1F]\s*(?:->|\u2192)?$/.test(line)
    || /^(\u9009\u62e9|\u4e0a\u4f20).*(\u6587\u4ef6|\u56fe\u7247)/.test(line);
}

function trimFollowupSuggestions(lines) {
  const kept = [];
  for (const line of lines) {
    if (kept.length > 0 && looksLikeFollowupSuggestion(line)) break;
    kept.push(line);
  }
  return kept;
}

function dedupeLines(lines) {
  const seen = new Set();
  const deduped = [];
  for (const line of lines) {
    const key = line.toLowerCase().replace(/\s+/g, " ").trim();
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(line);
  }
  return deduped;
}

function extractAfterPrompt(bodyText, prompt) {
  const lines = normalizeLines(bodyText);
  const promptText = prompt.trim();
  let promptIndex = -1;

  for (let index = lines.length - 1; index >= 0; index -= 1) {
    if (lines[index] === promptText || lines[index].includes(promptText)) {
      promptIndex = index;
      break;
    }
  }

  const candidates = (promptIndex >= 0 ? lines.slice(promptIndex + 1) : lines)
    .filter((line) => line !== promptText)
    .filter((line) => !isNoiseLine(line));

  return dedupeLines(trimFollowupSuggestions(candidates)).join("\n").trim();
}

function extractDelta(beforeText, afterText, prompt) {
  const beforeSet = new Set(normalizeLines(beforeText));
  const promptText = prompt.trim();
  const candidates = normalizeLines(afterText)
    .filter((line) => !beforeSet.has(line))
    .filter((line) => line !== promptText)
    .filter((line) => !line.includes(promptText))
    .filter((line) => !isNoiseLine(line));

  return dedupeLines(trimFollowupSuggestions(candidates)).join("\n").trim();
}

function isMinorGenerationIssue(text) {
  const compact = String(text || "").replace(/\s+/g, "");
  return /(\u56de\u590d)?\u751f\u6210.*\u9047\u5230.*\u5c0f\u95ee\u9898.*\u91cd\u65b0\u8bd5\u8bd5/.test(compact)
    || /\u70b9\u5c0f\u95ee\u9898.*\u91cd\u65b0\u8bd5\u8bd5/.test(compact);
}

async function getReplyText(page, beforeText, prompt) {
  const bodyText = await getBodyText(page);
  const deltaReply = extractDelta(beforeText, bodyText, prompt);
  const promptReply = extractAfterPrompt(bodyText, prompt);
  const reply = promptReply || deltaReply;
  return { bodyText, reply };
}

async function pastePrompt(page, input, prompt, timeoutMs) {
  await input.click({ timeout: timeoutMs });

  const domSet = await page.evaluate((text) => {
    const root = document.querySelector("#input-engine-container") || document;
    const textarea = root.querySelector("textarea") || document.querySelector("textarea");
    if (!textarea) return false;

    textarea.focus();
    const descriptor = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value");
    const setValue = descriptor && descriptor.set ? descriptor.set.bind(textarea) : (value) => { textarea.value = value; };
    setValue("");
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    setValue(text);
    textarea.dispatchEvent(new InputEvent("input", {
      bubbles: true,
      data: text,
      inputType: "insertText",
    }));
    textarea.dispatchEvent(new Event("change", { bubbles: true }));
    return textarea.value === text;
  }, prompt).catch(() => false);

  if (domSet) return;

  const origin = new URL(page.url()).origin;
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"], { origin }).catch(() => {});
  const pasted = await page.evaluate(async (text) => {
    await navigator.clipboard.writeText(text);
    return true;
  }, prompt).catch(() => false);

  if (pasted) {
    await page.keyboard.press(process.platform === "darwin" ? "Meta+V" : "Control+V");
    return;
  }

  await input.fill(prompt, { timeout: timeoutMs }).catch(async () => {
    await page.keyboard.insertText(prompt);
  });
}

async function clickSendButton(page) {
  const handle = await page.evaluateHandle(() => {
    const root = document.querySelector("#input-engine-container");
    const rootRect = root ? root.getBoundingClientRect() : { left: 0, top: window.innerHeight * 0.45, right: window.innerWidth, bottom: window.innerHeight };

    function visible(element) {
      const rect = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
    }

    const words = ["send", "\u53d1\u9001", "\u63d0\u4ea4"];
    const buttons = Array.from(document.querySelectorAll("button,[role='button']"))
      .filter((element) => {
        if (!visible(element) || element.disabled || element.getAttribute("aria-disabled") === "true") return false;
        const rect = element.getBoundingClientRect();
        return rect.left >= rootRect.left
          && rect.right <= rootRect.right + 2
          && rect.top >= rootRect.top - 2
          && rect.bottom <= rootRect.bottom + 2;
      })
      .map((element) => {
        const rect = element.getBoundingClientRect();
        const text = [
          element.innerText,
          element.getAttribute("aria-label"),
          element.getAttribute("title"),
        ].filter(Boolean).join(" ").toLowerCase();
        const directMatch = words.some((word) => text.includes(word.toLowerCase()));
        const rightEdgeControl = rect.left > rootRect.right - 70 && rect.bottom > rootRect.bottom - 55 && element.querySelector("svg");
        const nonSendText = /more|\u66f4\u591a|\u8bed\u97f3|\u9ea6\u514b\u98ce/.test(text);
        return { element, score: (directMatch ? 10 : 0) + (rightEdgeControl && !nonSendText ? 5 : 0) + rect.left / 10000 };
      })
      .filter((item) => item.score > 0)
      .sort((a, b) => b.score - a.score);

    return buttons[0]?.element || null;
  });

  const element = handle.asElement();
  if (!element) return false;
  await element.click({ timeout: 5000 }).catch(() => {});
  return true;
}

async function clickNewChat(page) {
  const handle = await page.evaluateHandle(() => {
    function visible(element) {
      const rect = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
    }

    const newChatText = "\u65b0\u5bf9\u8bdd";
    const candidates = Array.from(document.querySelectorAll("button,[role='button'],a,div"))
      .filter((element) => visible(element))
      .map((element) => ({ element, rect: element.getBoundingClientRect(), text: (element.innerText || element.getAttribute("aria-label") || element.getAttribute("title") || "").trim() }))
      .filter((item) => item.text === newChatText && item.rect.left < 290 && item.rect.top < 140)
      .sort((a, b) => (a.rect.width * a.rect.height) - (b.rect.width * b.rect.height));

    return candidates[0]?.element || null;
  });

  const element = handle.asElement();
  if (!element) return false;
  await element.click({ timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(1000);
  return true;
}

async function inputStillContainsPrompt(page, prompt) {
  return page.evaluate((text) => {
    const root = document.querySelector("#input-engine-container") || document;
    const textarea = root.querySelector("textarea") || document.querySelector("textarea");
    return Boolean(textarea && textarea.value && textarea.value.includes(text));
  }, prompt).catch(() => false);
}

function normalizeImagePaths(values) {
  const allowed = new Set([".png", ".jpg", ".jpeg", ".webp"]);
  const imagePaths = [];
  for (const value of values) {
    for (const part of String(value || "").split(";")) {
      const trimmed = part.trim().replace(/^"(.*)"$/, "$1");
      if (!trimmed) continue;
      const resolved = path.resolve(trimmed);
      if (!fs.existsSync(resolved)) {
        throw new Error(`Image file does not exist: ${resolved}`);
      }
      const stat = fs.statSync(resolved);
      if (!stat.isFile()) {
        throw new Error(`Image path is not a file: ${resolved}`);
      }
      const ext = path.extname(resolved).toLowerCase();
      if (!allowed.has(ext)) {
        throw new Error(`Unsupported image type ${ext || "(none)"} for ${resolved}. Use PNG, JPG, JPEG, or WEBP.`);
      }
      imagePaths.push(resolved);
    }
  }
  return Array.from(new Set(imagePaths));
}

async function setFilesOnExistingInput(page, imagePaths) {
  const inputs = await page.$$("input[type='file']").catch(() => []);
  for (const input of inputs) {
    const accept = (await input.getAttribute("accept").catch(() => "") || "").toLowerCase();
    if (accept && ![".png", ".jpg", ".jpeg", ".webp", "image"].some((token) => accept.includes(token))) {
      continue;
    }
    await input.setInputFiles(imagePaths);
    return true;
  }
  return false;
}

async function clickAttachButton(page) {
  const handle = await page.evaluateHandle(() => {
    const root = document.querySelector("#input-engine-container");
    if (!root) return null;
    const rootRect = root.getBoundingClientRect();

    function visible(element) {
      const rect = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
    }

    const buttons = Array.from(root.querySelectorAll("button,[role='button'],div"))
      .filter((element) => visible(element))
      .map((element) => {
        const rect = element.getBoundingClientRect();
        const text = [
          element.innerText,
          element.getAttribute("aria-label"),
          element.getAttribute("title"),
          element.outerHTML,
        ].filter(Boolean).join(" ").toLowerCase();
        const plusArea = rect.left < rootRect.left + 70 && rect.bottom > rootRect.bottom - 55;
        const uploadText = /upload|attach|\u4e0a\u4f20|\u9644\u4ef6|\u56fe\u7247|\u6587\u4ef6/.test(text);
        const hasSvg = Boolean(element.querySelector("svg"));
        return { element, score: (plusArea && hasSvg ? 10 : 0) + (uploadText ? 5 : 0) - (rect.width * rect.height) / 100000 };
      })
      .filter((item) => item.score > 0)
      .sort((a, b) => b.score - a.score);

    return buttons[0]?.element || null;
  });

  const element = handle.asElement();
  if (!element) return false;
  await element.click({ timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(300);
  return true;
}

async function clickUploadMenuItem(page, imagePaths) {
  const chooserPromise = page.waitForEvent("filechooser", { timeout: 5000 }).catch(() => null);
  const handle = await page.evaluateHandle(() => {
    function visible(element) {
      const rect = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
    }

    const labels = [
      "\u4e0a\u4f20\u6587\u4ef6\u6216\u56fe\u7247",
      "\u4e0a\u4f20\u56fe\u7247",
      "\u4e0a\u4f20\u6587\u4ef6",
      "\u9009\u62e9\u56fe\u7247",
    ];
    const candidates = Array.from(document.querySelectorAll("button,[role='menuitem'],[role='button'],div,span"))
      .filter((element) => visible(element))
      .map((element) => ({ element, text: (element.innerText || element.textContent || "").trim() }))
      .filter((item) => labels.some((label) => item.text.includes(label)))
      .sort((a, b) => a.text.length - b.text.length);
    return candidates[0]?.element || null;
  });

  const element = handle.asElement();
  if (element) {
    await element.click({ timeout: 5000 }).catch(() => {});
  }
  const chooser = await chooserPromise;
  if (!chooser) return false;
  await chooser.setFiles(imagePaths);
  return true;
}

async function uploadImages(page, imagePaths, timeoutMs) {
  if (!imagePaths.length) return false;

  if (await setFilesOnExistingInput(page, imagePaths)) {
    await page.waitForTimeout(Math.min(3000, Math.max(1000, timeoutMs / 10)));
    return true;
  }

  await clickAttachButton(page);
  if (await setFilesOnExistingInput(page, imagePaths)) {
    await page.waitForTimeout(Math.min(3000, Math.max(1000, timeoutMs / 10)));
    return true;
  }

  if (await clickUploadMenuItem(page, imagePaths)) {
    await page.waitForTimeout(Math.min(3000, Math.max(1000, timeoutMs / 10)));
    return true;
  }

  throw new Error("Could not find or activate Doubao image upload control.");
}

async function sendPrompt(page, prompt, timeoutMs) {
  const input = await visibleLocator(
    page,
    [
      "textarea",
      "#input-engine-container",
      "[class*='input-content-container']",
      "[class*='textarea-wrapper']",
      "[contenteditable='true']",
      "[role='textbox']",
      "div[contenteditable]",
    ],
    timeoutMs,
  );

  if (!input) {
    throw new Error("Could not find Doubao chat input. Login, CAPTCHA, or a changed UI may be blocking automation.");
  }

  await pastePrompt(page, input, prompt, timeoutMs);
  await page.waitForTimeout(300);

  const clicked = await clickSendButton(page);
  if (!clicked) {
    await page.keyboard.press("Enter");
  }

  await page.waitForTimeout(500);
  if (await inputStillContainsPrompt(page, prompt)) {
    await page.keyboard.press("Enter").catch(() => {});
  }
}

async function main() {
  if (process.argv.includes("--help") || process.argv.includes("-h")) {
    console.log([
      "Usage:",
      "  node doubao_quick_send.js --prompt \"hello\" [--image path/to/image.png] [--cdp-url http://127.0.0.1:9222] [--wait-ms 10000] [--cooldown-ms 12000] [--new-chat]",
      "",
      "Connects to an existing Chrome DevTools endpoint, reuses an existing Doubao chat by default, optionally uploads images, sends a prompt, waits 10 seconds by default, then prints JSON.",
    ].join("\n"));
    return;
  }

  const cdpUrl = arg("cdp-url", process.env.DOUBAO_CDP_URL || process.env.CHROME_DIDY_CDP_URL || "http://127.0.0.1:9222");
  const doubaoUrl = arg("url", "https://www.doubao.com/chat/");
  const prompt = arg("prompt", "").trim();
  const newChat = process.argv.includes("--new-chat");
  const reuseCurrentChat = !newChat;
  const waitMs = numberArg("wait-ms", 10000);
  const timeoutMs = numberArg("timeout-ms", 30000);
  const cooldownMs = numberArg("cooldown-ms", Number(process.env.DOUBAO_COOLDOWN_MS || 12000));
  const screenshot = arg("screenshot");
  const replyOut = arg("reply-out");
  const bodyOut = arg("body-out");
  const stateOut = arg("state-out");
  const imagePaths = normalizeImagePaths([...argValues("image"), ...argValues("image-path")]);

  if (!prompt) throw new Error("Missing required --prompt value.");

  let page;
  let beforeText = "";
  let releaseLock = null;
  let cooldownWaitMs = 0;
  const browser = await chromium.connectOverCDP(cdpUrl, { timeout: timeoutMs });
  try {
    releaseLock = await acquireSendLock(timeoutMs);
    cooldownWaitMs = await applyCooldown(cooldownMs);

    const context = browser.contexts()[0] || await browser.newContext();
    page = context.pages().find((candidate) => /doubao\.com\/chat/.test(candidate.url()));
    if (!page) page = await context.newPage();

    if (!/doubao\.com\/chat/.test(page.url())) {
      await page.goto(doubaoUrl, { waitUntil: "domcontentloaded", timeout: timeoutMs });
    }

    await page.bringToFront().catch(() => {});
    await page.waitForLoadState("domcontentloaded", { timeout: timeoutMs }).catch(() => {});
    await assertNoHumanGate(page, "page load");
    if (!reuseCurrentChat) {
      await clickNewChat(page).catch(() => false);
      await assertNoHumanGate(page, "new chat");
    }

    beforeText = await assertNoHumanGate(page, "before send");
    await uploadImages(page, imagePaths, timeoutMs);
    await assertNoHumanGate(page, "after image upload");
    await sendPrompt(page, prompt, timeoutMs);
    recordSendTimestamp();
    await page.waitForTimeout(waitMs);
    let { bodyText, reply } = await getReplyText(page, beforeText, prompt);
    const recovery = {
      minorGenerationIssue: isMinorGenerationIssue(reply),
      continueSent: false,
      prompt: "",
    };

    if (recovery.minorGenerationIssue) {
      const continuePrompt = "\u7ee7\u7eed";
      recovery.continueSent = true;
      recovery.prompt = continuePrompt;
      const retryBeforeText = bodyText;
      await sendPrompt(page, continuePrompt, timeoutMs);
      recordSendTimestamp();
      await page.waitForTimeout(waitMs);
      const retried = await getReplyText(page, retryBeforeText, continuePrompt);
      bodyText = retried.bodyText;
      reply = retried.reply || reply;
    }

    const screenshotPath = screenshot
      ? (fs.mkdirSync(path.dirname(path.resolve(screenshot)), { recursive: true }), await page.screenshot({ path: screenshot, fullPage: true }), screenshot)
      : "";
    const replyPath = writeFile(replyOut, reply);
    const bodyPath = writeFile(bodyOut, bodyText);
    const pageTitle = await page.title();
    const statePath = writeJson(stateOut, {
      lastGoodCdpUrl: cdpUrl,
      lastOkAt: new Date().toISOString(),
      lastUrl: page.url(),
      lastPromptLength: prompt.length,
      lastImageCount: imagePaths.length,
      updatedBy: "doubao_quick_send",
    });

    console.log(JSON.stringify({
      ok: Boolean(reply),
      sent: true,
      waitMs,
      cooldownMs,
      cooldownWaitMs,
      chatMode: reuseCurrentChat ? "reuse-existing-chat" : "new-chat",
      url: page.url(),
      title: pageTitle,
      prompt,
      images: imagePaths,
      recovery,
      reply,
      evidence: {
        screenshot: screenshotPath,
        reply: replyPath,
        body: bodyPath,
        state: statePath,
      },
    }, null, 2));
  } catch (error) {
    const bodyText = page ? await getBodyText(page).catch(() => beforeText) : beforeText;
    const screenshotPath = page && screenshot
      ? (fs.mkdirSync(path.dirname(path.resolve(screenshot)), { recursive: true }), await page.screenshot({ path: screenshot, fullPage: true }).catch(() => null), screenshot)
      : "";
    const bodyPath = writeFile(bodyOut, bodyText);
    console.error(JSON.stringify({
      ok: false,
      sent: false,
      error: error.message,
      blocker: error.blocker || "",
      url: page ? page.url() : "",
      title: page ? await page.title().catch(() => "") : "",
      images: typeof imagePaths !== "undefined" ? imagePaths : [],
      evidence: {
        screenshot: screenshotPath,
        body: bodyPath,
      },
      stack: error.stack,
    }, null, 2));
    process.exitCode = 1;
  } finally {
    if (releaseLock) releaseLock();
    await browser.close();
  }
}

main().catch((error) => {
  console.error(JSON.stringify({
    ok: false,
    sent: false,
    error: error.message,
    stack: error.stack,
  }, null, 2));
  process.exit(1);
});
