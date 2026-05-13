import { writeFileSync } from "node:fs";

const targetMid = process.env.JUYA_MID || "285286947";
const targetDate =
  process.env.JUYA_DAILY_DATE ||
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());

const maxCandidates = Number(process.env.JUYA_MAX_CANDIDATES || 40);
const outputPath = process.env.JUYA_LOOKUP_RESULT || "juya-today-daily-result.json";
const requireToday = process.env.JUYA_REQUIRE_TODAY !== "0";
const userAgent =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
  "Chrome/124.0.0.0 Safari/537.36";

const headers = {
  "User-Agent": userAgent,
  Referer: "https://www.bilibili.com/",
  "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
};

const searchQueries = [
  `橘鸦Juya AI 早报 ${targetDate}`,
  `橘鸦Juya ${targetDate}`,
  `site:bilibili.com/video 橘鸦Juya AI 早报 ${targetDate}`,
];

function decodeEscapes(value = "") {
  return String(value)
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
    /AI/i.test(title) &&
    /(早报|日报)/.test(title) &&
    !/(转载|切片|合集|直播回放)/.test(title)
  );
}

function normalizeVideo(video) {
  const pubdate = video.pubdate ? Number(video.pubdate) : null;
  return {
    bvid: video.bvid,
    title: video.title || "",
    author: video.author || "",
    mid: String(video.mid || ""),
    description: video.description || "",
    pubdate,
    published_date: shanghaiDate(pubdate),
    published_at: shanghaiTime(pubdate),
    url: video.bvid ? `https://www.bilibili.com/video/${video.bvid}` : "",
    sources: video.sources || [],
    api_url: video.api_url || "",
  };
}

function addCandidate(map, candidate) {
  if (!candidate?.bvid) return;
  const current = map.get(candidate.bvid);
  if (!current) {
    map.set(candidate.bvid, normalizeVideo(candidate));
    return;
  }
  const mergedSources = [...(current.sources || []), ...(candidate.sources || [])];
  map.set(candidate.bvid, {
    ...current,
    ...normalizeVideo({
      ...current,
      ...Object.fromEntries(
        Object.entries(candidate).filter(([, value]) => value !== undefined && value !== null && value !== ""),
      ),
      sources: mergedSources,
    }),
  });
}

function extractVideos(html, source) {
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

    results.push(
      normalizeVideo({
        bvid,
        title,
        author:
          field(windowText, "author") ||
          decodeEscapes((windowText.match(/class="bili-video-card__info--author"[^>]*>([^<]+)<\/span>/) || [])[1] || ""),
        mid: numericField(windowText, "mid") || ((windowText.match(/space\.bilibili\.com\/(\d+)/) || [])[1] || ""),
        description: field(windowText, "description"),
        pubdate: pubdate ? Number(pubdate) : null,
        sources: [source],
      }),
    );
  }

  return results;
}

async function fetchJson(url, kind, attempts) {
  const attempt = { kind, url };
  try {
    const response = await fetch(url, { headers });
    attempt.status = response.status;
    const text = await response.text();
    attempt.bytes = text.length;
    try {
      attempt.json_code = JSON.parse(text)?.code;
      return { ok: response.ok, text, json: JSON.parse(text), attempt };
    } catch {
      attempt.parse_error = "not_json";
      return { ok: response.ok, text, json: null, attempt };
    }
  } catch (error) {
    attempt.error = String(error?.message || error);
    return { ok: false, text: "", json: null, attempt };
  } finally {
    attempts.push(attempt);
  }
}

async function fetchSpaceArchive(attempts, candidates) {
  const urls = [
    `https://api.bilibili.com/x/space/wbi/arc/search?mid=${targetMid}&ps=20&pn=1&order=pubdate&platform=web`,
    `https://api.bilibili.com/x/space/arc/search?mid=${targetMid}&ps=20&pn=1&order=pubdate`,
  ];

  for (const url of urls) {
    const { json } = await fetchJson(url, "space_archive", attempts);
    const list = json?.data?.list?.vlist || json?.data?.list?.archives || [];
    if (!Array.isArray(list)) continue;
    for (const item of list) {
      addCandidate(candidates, {
        bvid: item.bvid,
        title: item.title,
        author: item.author || "橘鸦Juya",
        mid: item.mid || targetMid,
        description: item.description || item.desc,
        pubdate: item.pubdate || item.created,
        sources: [{ kind: "space_archive", url }],
      });
    }
  }
}

async function fetchSearchPages(attempts, candidates) {
  for (const query of searchQueries) {
    const url = `https://search.bilibili.com/all?keyword=${encodeURIComponent(query)}`;
    const attempt = { kind: "bilibili_search", query, url };
    try {
      const response = await fetch(url, { headers });
      const text = await response.text();
      attempt.status = response.status;
      attempt.bytes = text.length;
      attempts.push(attempt);
      if (response.ok) {
        for (const video of extractVideos(text, { kind: "bilibili_search", query, url })) {
          addCandidate(candidates, video);
        }
      }
    } catch (error) {
      attempt.error = String(error?.message || error);
      attempts.push(attempt);
    }
  }
}

async function enrichVideo(video) {
  const apiUrl = `https://api.bilibili.com/x/web-interface/view?bvid=${video.bvid}`;
  try {
    const response = await fetch(apiUrl, {
      headers: {
        ...headers,
        Referer: `https://www.bilibili.com/video/${video.bvid}/`,
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
      sources: [...(video.sources || []), { kind: "view_api", url: apiUrl }],
      api_url: apiUrl,
    });

    const sameAuthor = enriched.mid === targetMid;
    const sameDate = enriched.published_date === targetDate || enriched.title.includes(targetDate);
    const daily = looksLikeJuyaDaily(enriched.title);
    const eligible = sameAuthor && daily && (!requireToday || sameDate);

    return {
      ...enriched,
      verified: true,
      validation: {
        sameAuthor,
        sameDate,
        daily,
        requireToday,
        eligible,
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

const attempts = [];
const candidates = new Map();

await fetchSpaceArchive(attempts, candidates);
await fetchSearchPages(attempts, candidates);

const enrichedVideos = [];
for (const video of Array.from(candidates.values()).slice(0, maxCandidates)) {
  enrichedVideos.push(await enrichVideo(video));
}

const eligibleMatches = enrichedVideos
  .filter((video) => video.validation?.eligible)
  .sort((a, b) => Number(b.pubdate || 0) - Number(a.pubdate || 0));
const sameAuthorVideos = enrichedVideos
  .filter((video) => video.verified && video.mid === targetMid)
  .sort((a, b) => Number(b.pubdate || 0) - Number(a.pubdate || 0));
const best = eligibleMatches[0] || null;
const sourceKinds = new Set(best?.sources?.map((source) => source.kind) || []);

const result = {
  found: Boolean(best),
  target_date: targetDate,
  target_mid: targetMid,
  require_today: requireToday,
  selection_rule:
    "Prefer Bilibili space archive when available; fallback to search only after mandatory x/web-interface/view verification. Require owner.mid=285286947, AI daily title, and target date when enabled; choose newest pubdate.",
  source_priority: sourceKinds.has("space_archive") ? "space_archive_verified" : best ? "search_fallback_view_api_verified" : "none",
  result: best,
  attempts,
  candidates: enrichedVideos,
  latest_verified_same_author: sameAuthorVideos[0] || null,
  generated_at: shanghaiTime(Math.floor(Date.now() / 1000)),
};

writeFileSync(outputPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");

if (best) {
  console.log("FOUND=yes");
  console.log(`TITLE=${best.title}`);
  console.log(`BVID=${best.bvid}`);
  console.log(`URL=https://www.bilibili.com/video/${best.bvid}`);
  console.log(`AUTHOR=${best.author}`);
  console.log(`MID=${best.mid}`);
  console.log(`PUBLISHED_AT=${best.published_at}`);
  console.log(`SOURCE_PRIORITY=${result.source_priority}`);
} else {
  console.log("FOUND=no");
  console.log(`TARGET_DATE=${targetDate}`);
  console.log(`CANDIDATES=${candidates.size}`);
  if (sameAuthorVideos[0]) {
    console.log(`LATEST_SAME_AUTHOR=${sameAuthorVideos[0].bvid}`);
    console.log(`LATEST_SAME_AUTHOR_DATE=${sameAuthorVideos[0].published_date}`);
  }
  console.log(`DETAIL_FILE=${outputPath}`);
  process.exitCode = 2;
}
