import { writeFileSync } from "node:fs";

const targetMid = "285286947";
const targetDate =
  process.env.JUYA_DAILY_DATE ||
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());

const maxCandidates = Number(process.env.JUYA_MAX_CANDIDATES || 30);
const requireToday = process.env.JUYA_REQUIRE_TODAY !== "0";
const resultPath = process.env.JUYA_LOOKUP_RESULT || "juya-today-daily-result.json";
const userAgent =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
  "Chrome/124.0.0.0 Safari/537.36";

const queries = [
  `\u6a58\u9e26Juya AI \u65e9\u62a5 ${targetDate}`,
  `\u6a58\u9e26Juya ${targetDate}`,
  `site:bilibili.com/video \u6a58\u9e26Juya AI \u65e9\u62a5 ${targetDate}`,
];

function decodeEscapes(value = "") {
  return value
    .replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
    .replace(/\\\//g, "/")
    .replace(/\\"/g, '"')
    .replace(/<[^>]*>/g, "")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .trim();
}

function shanghaiParts(seconds) {
  if (!seconds) return {};
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  })
    .formatToParts(new Date(Number(seconds) * 1000))
    .reduce((acc, part) => {
      acc[part.type] = part.value;
      return acc;
    }, {});
}

function shanghaiTime(seconds) {
  const parts = shanghaiParts(seconds);
  if (!parts.year) return "";
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second} +08:00`;
}

function shanghaiDate(seconds) {
  const parts = shanghaiParts(seconds);
  return parts.year ? `${parts.year}-${parts.month}-${parts.day}` : "";
}

function field(windowText, name) {
  const pattern = new RegExp(`"${name}"\\s*:\\s*"((?:\\\\.|[^"\\\\])*)"`);
  const match = windowText.match(pattern);
  return match ? decodeEscapes(match[1]) : "";
}

function numericField(windowText, name) {
  const pattern = new RegExp(`"${name}"\\s*:\\s*(\\d+)`);
  const match = windowText.match(pattern);
  return match ? match[1] : "";
}

function looksLikeJuyaDaily(title = "") {
  return (
    title.includes("AI") &&
    (title.includes("\u65e9\u62a5") || title.includes("\u65e5\u62a5")) &&
    !title.includes("\u8f6c\u8f7d")
  );
}

function normalizeVideo(video) {
  const pubdate = video.pubdate ? Number(video.pubdate) : null;
  return {
    ...video,
    mid: String(video.mid || ""),
    pubdate,
    published_date: shanghaiDate(pubdate),
    published_at: shanghaiTime(pubdate),
    url: `https://www.bilibili.com/video/${video.bvid}`,
  };
}

function extractVideos(html, sourceUrl) {
  const results = [];
  const seen = new Set();
  const bvidPattern = /(?:"bvid"\s*:\s*"|\/video\/)(BV[0-9A-Za-z]+)(?:"|\/)/g;
  let match;

  while ((match = bvidPattern.exec(html))) {
    const bvid = match[1];
    if (seen.has(bvid)) continue;
    seen.add(bvid);

    const start = Math.max(0, match.index - 12000);
    const end = Math.min(html.length, match.index + 12000);
    const windowText = html.slice(start, end);
    const pubdate = numericField(windowText, "pubdate");
    const title =
      field(windowText, "title") ||
      decodeEscapes((windowText.match(/<h3[^>]*title="([^"]+)"/) || [])[1] || "") ||
      decodeEscapes((windowText.match(/<img[^>]*alt="([^"]+)"/) || [])[1] || "");
    const author =
      field(windowText, "author") ||
      decodeEscapes((windowText.match(/class="bili-video-card__info--author"[^>]*>([^<]+)<\/span>/) || [])[1] || "");
    const mid =
      numericField(windowText, "mid") ||
      ((windowText.match(/space\.bilibili\.com\/(\d+)/) || [])[1] || "");
    const description = field(windowText, "description");

    results.push(
      normalizeVideo({
        bvid,
        title,
        author,
        mid,
        description,
        pubdate: pubdate ? Number(pubdate) : null,
        source_url: sourceUrl,
        source_kind: "bilibili_search",
      }),
    );
  }

  return results;
}

async function enrichVideo(video) {
  const apiUrl = `https://api.bilibili.com/x/web-interface/view?bvid=${video.bvid}`;
  try {
    const response = await fetch(apiUrl, {
      headers: {
        "User-Agent": userAgent,
        "Referer": `https://www.bilibili.com/video/${video.bvid}/`,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
      },
    });
    const data = await response.json();
    if (data?.code !== 0 || !data?.data) {
      return {
        ...video,
        verified: false,
        verify_error: `view_api_code=${data?.code ?? "unknown"} message=${data?.message ?? ""}`,
        api_url: apiUrl,
      };
    }

    const item = data.data;
    const enriched = normalizeVideo({
      ...video,
      title: item.title || video.title,
      author: item.owner?.name || video.author,
      mid: String(item.owner?.mid || video.mid),
      description: item.desc || video.description,
      pubdate: item.pubdate || video.pubdate,
      api_url: apiUrl,
    });

    const sameAuthor = enriched.mid === targetMid;
    const sameDate = enriched.published_date === targetDate || enriched.title.includes(targetDate);
    const daily = looksLikeJuyaDaily(enriched.title);

    return {
      ...enriched,
      verified: true,
      validation: {
        sameAuthor,
        sameDate,
        daily,
        eligible: sameAuthor && daily && (!requireToday || sameDate),
      },
    };
  } catch (error) {
    return {
      ...video,
      verified: false,
      verify_error: String(error?.message || error),
      api_url: apiUrl,
    };
  }
}

async function fetchSearchPage(query) {
  const url = `https://search.bilibili.com/all?keyword=${encodeURIComponent(query)}`;
  const response = await fetch(url, {
    headers: {
      "User-Agent": userAgent,
      "Referer": "https://www.bilibili.com/",
      "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    },
  });
  const text = await response.text();
  return { query, url, status: response.status, text };
}

const attempts = [];
const allVideos = [];

for (const query of queries) {
  const page = await fetchSearchPage(query);
  attempts.push({ query, url: page.url, status: page.status, bytes: page.text.length });
  if (page.status >= 200 && page.status < 300) {
    allVideos.push(...extractVideos(page.text, page.url));
  }
}

const uniqueVideos = Array.from(new Map(allVideos.map((item) => [item.bvid, item])).values());
const enrichedVideos = [];
for (const video of uniqueVideos.slice(0, maxCandidates)) {
  enrichedVideos.push(await enrichVideo(video));
}

const eligibleMatches = enrichedVideos
  .filter((video) => video.validation?.eligible)
  .sort((a, b) => Number(b.pubdate || 0) - Number(a.pubdate || 0));
const sameAuthorVideos = enrichedVideos
  .filter((video) => video.verified && video.mid === targetMid)
  .sort((a, b) => Number(b.pubdate || 0) - Number(a.pubdate || 0));
const best = eligibleMatches[0] || null;

const result = {
  found: Boolean(best),
  target_date: targetDate,
  target_mid: targetMid,
  require_today: requireToday,
  selection_rule:
    "Only choose videos verified by x/web-interface/view with owner.mid=285286947, AI daily title, target date when required, sorted by pubdate desc.",
  result: best,
  attempts,
  candidates: enrichedVideos,
  latest_verified_same_author: sameAuthorVideos[0] || null,
  generated_at: shanghaiTime(Math.floor(Date.now() / 1000)),
};

writeFileSync(resultPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");

if (best) {
  console.log("FOUND=yes");
  console.log(`TITLE=${best.title}`);
  console.log(`BVID=${best.bvid}`);
  console.log(`URL=https://www.bilibili.com/video/${best.bvid}`);
  console.log(`AUTHOR=${best.author}`);
  console.log(`MID=${best.mid}`);
  console.log(`PUBLISHED_AT=${best.published_at}`);
  console.log(`SOURCE=${best.source_url}`);
} else {
  console.log("FOUND=no");
  console.log(`TARGET_DATE=${targetDate}`);
  console.log(`CANDIDATES=${uniqueVideos.length}`);
  if (sameAuthorVideos[0]) {
    console.log(`LATEST_SAME_AUTHOR=${sameAuthorVideos[0].bvid}`);
    console.log(`LATEST_SAME_AUTHOR_DATE=${sameAuthorVideos[0].published_date}`);
  }
  console.log(`DETAIL_FILE=${resultPath}`);
  process.exitCode = 2;
}
