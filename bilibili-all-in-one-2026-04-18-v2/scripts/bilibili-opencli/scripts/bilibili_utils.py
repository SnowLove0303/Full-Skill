# -*- coding: utf-8 -*-
"""OpenCLI Bilibili 命令封装"""
import subprocess
import json
import re
import os
import shutil
import hashlib
import time
import urllib.parse
import urllib.request
from datetime import datetime

WBI_MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]

def resolve_opencli_cmd() -> str | None:
    """Resolve opencli without depending on a hard-coded user profile."""
    if os.environ.get("BILIBILI_DISABLE_OPENCLI") in ("1", "true", "TRUE", "yes", "YES"):
        return None
    return (
        os.environ.get("OPENCLI_CMD")
        or shutil.which("opencli")
        or shutil.which("opencli.cmd")
    )

def run(args: list[str], timeout=60) -> dict:
    """执行 opencli bilibili 命令，返回 JSON 结果"""
    opencli_cmd = resolve_opencli_cmd()
    if not opencli_cmd:
        return {"_raw": "", "_stderr": "opencli not found; using fallback APIs when available", "_returncode": 127}
    cmd = [opencli_cmd] + args
    env = os.environ.copy()
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
        encoding='utf-8', errors='replace', env=env
    )
    # 直接解析完整 stdout 为 JSON
    try:
        return json.loads(result.stdout.strip())
    except Exception:
        pass
    return {"_raw": result.stdout, "_stderr": result.stderr, "_returncode": result.returncode}

def search_videos(query: str, limit=20, page=1) -> list[dict]:
    """搜索视频"""
    args = [
        "bilibili", "search", query,
        "--type", "video",
        "--limit", str(limit),
        "--page", str(page),
        "--format", "json"
    ]
    data = run(args)
    if isinstance(data, list) and data:
        return data
    return _search_videos_public_api(query, limit=limit, page=page)

def get_user_videos(uid: str, limit=20, page=1, order="pubdate") -> list[dict]:
    """获取 UP 主视频列表"""
    args = [
        "bilibili", "user-videos", uid,
        "--limit", str(limit),
        "--page", str(page),
        "--order", order,
        "--format", "json"
    ]
    data = run(args)
    if isinstance(data, list) and data:
        return data
    return _get_user_videos_public_api(uid, limit=limit, page=page, order=order)

def _get_json(url: str, referer: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": referer,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))

def _get_wbi_mixin_key() -> str:
    data = _get_json("https://api.bilibili.com/x/web-interface/nav", "https://www.bilibili.com/")
    wbi_img = (data.get("data") or {}).get("wbi_img") or {}
    img_key = os.path.splitext(os.path.basename(wbi_img.get("img_url", "")))[0]
    sub_key = os.path.splitext(os.path.basename(wbi_img.get("sub_url", "")))[0]
    raw = img_key + sub_key
    return "".join(raw[i] for i in WBI_MIXIN_KEY_ENC_TAB if i < len(raw))[:32]

def _wbi_signed_url(base_url: str, params: dict) -> str:
    params = {k: str(v) for k, v in params.items() if v is not None}
    params["wts"] = str(int(time.time()))
    mixin_key = _get_wbi_mixin_key()
    query = urllib.parse.urlencode(sorted(params.items()))
    params["w_rid"] = hashlib.md5((query + mixin_key).encode("utf-8")).hexdigest()
    return base_url + "?" + urllib.parse.urlencode(sorted(params.items()))

def _format_pubdate(ts) -> str:
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""

def _clean_html(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value or "")

def _search_videos_public_api(query: str, limit=20, page=1) -> list[dict]:
    """Fallback for environments where opencli returns no JSON results."""
    encoded = urllib.parse.quote(query)
    direct_url = (
        "https://api.bilibili.com/x/web-interface/search/type"
        f"?search_type=video&keyword={encoded}&page={page}"
    )
    videos = []
    for attempt in range(3):
        try:
            direct_data = _get_json(direct_url, "https://search.bilibili.com/")
        except Exception:
            direct_data = {}
        for rank, item in enumerate((direct_data.get("data") or {}).get("result") or [], 1):
            bvid = item.get("bvid") or extract_bvid(item.get("arcurl", ""))
            if not bvid or not str(bvid).startswith("BV"):
                continue
            videos.append({
                "rank": rank,
                "bvid": bvid,
                "title": _clean_html(item.get("title", "")),
                "author": item.get("author", ""),
                "plays": item.get("play", 0),
                "date": _format_pubdate(item.get("pubdate")),
                "url": f"https://www.bilibili.com/video/{bvid}/",
                "source": "public_api",
            })
            if len(videos) >= limit:
                return videos
        if videos:
            return videos
        if attempt < 2:
            time.sleep(0.5 * (attempt + 1))

    url = (
        "https://api.bilibili.com/x/web-interface/search/type"
        f"?search_type=bili_user&keyword={encoded}&page={page}"
    )
    try:
        data = _get_json(url, "https://search.bilibili.com/")
    except Exception:
        return []

    videos = []
    for user in (data.get("data") or {}).get("result") or []:
        author = user.get("uname", "")
        for rank, item in enumerate(user.get("res") or [], 1):
            bvid = item.get("bvid") or extract_bvid(item.get("arcurl", ""))
            if not bvid or not str(bvid).startswith("BV"):
                continue
            videos.append({
                "rank": rank,
                "bvid": bvid,
                "title": _clean_html(item.get("title", "")),
                "author": author,
                "plays": item.get("play", 0),
                "date": _format_pubdate(item.get("pubdate")),
                "url": f"https://www.bilibili.com/video/{bvid}/",
                "source": "public_api",
            })
            if len(videos) >= limit:
                return videos
    return videos

def _get_user_videos_public_api(uid: str, limit=20, page=1, order="pubdate") -> list[dict]:
    """Fallback for UP video lists using Bilibili's signed web API."""
    base_url = "https://api.bilibili.com/x/space/wbi/arc/search"
    try:
        url = _wbi_signed_url(base_url, {
            "mid": uid,
            "ps": limit,
            "tid": 0,
            "pn": page,
            "order": order,
            "platform": "web",
            "web_location": 1550101,
        })
        data = _get_json(url, f"https://space.bilibili.com/{uid}/video")
    except Exception:
        return []

    archives = (((data.get("data") or {}).get("list") or {}).get("vlist") or [])
    videos = []
    for rank, item in enumerate(archives, 1):
        bvid = item.get("bvid")
        if not bvid:
            continue
        videos.append({
            "rank": rank,
            "bvid": bvid,
            "title": item.get("title", ""),
            "author": item.get("author", ""),
            "plays": item.get("play", 0),
            "date": _format_pubdate(item.get("created")),
            "url": f"https://www.bilibili.com/video/{bvid}/",
            "source": "public_api",
        })
    return videos

def download_video(bvid: str, output_dir: str, quality="best") -> dict:
    """下载视频"""
    args = [
        "bilibili", "download", bvid,
        "--output", output_dir,
        "--quality", quality,
        "--format", "json"
    ]
    data = run(args, timeout=300)
    return data

def get_subtitle(bvid: str, lang="zh-CN") -> list[dict]:
    """获取字幕"""
    args = [
        "bilibili", "subtitle", bvid,
        "--lang", lang,
        "--format", "json"
    ]
    data = run(args)
    if isinstance(data, list):
        return data
    return []

def extract_bvid(url_or_bvid: str) -> str:
    """从 URL 或 BV 号提取 BV"""
    if url_or_bvid.startswith('BV'):
        return url_or_bvid
    m = re.search(r'BV[\w]+', url_or_bvid)
    return m.group(0) if m else url_or_bvid

def normalize_video_info(raw: dict) -> dict:
    """统一不同来源的视频信息格式"""
    # 用户视频列表格式（优先判断，有 plays 字段）
    if 'plays' in raw and 'rank' in raw:
        bvid = raw.get('bvid') or extract_bvid(raw.get('url', ''))
        title = raw.get('title', '')
        title = re.sub(r'[\\/:*?"<>|]', '_', title)
        return {
            'bvid': bvid,
            'title': title,
            'author': raw.get('author', ''),
            'plays': raw.get('plays', 0),
            'date': raw.get('date', ''),
            'url': raw.get('url', ''),
            'source': raw.get('source', 'user')
        }
    # 搜索结果格式（有 author 字段）
    if 'url' in raw and 'rank' in raw and 'author' in raw:
        bvid = raw.get('bvid') or extract_bvid(raw.get('url', ''))
        title = raw.get('title', '')
        title = re.sub(r'[\\/:*?"<>|]', '_', title)
        return {
            'bvid': bvid,
            'title': title,
            'author': raw.get('author', ''),
            'plays': raw.get('plays', 0),
            'date': raw.get('date', ''),
            'score': raw.get('score', 0),
            'url': raw.get('url', ''),
            'source': raw.get('source', 'search')
        }
    return raw

def match_date(videos: list[dict], target_date: str) -> list[dict]:
    """按日期过滤视频"""
    if not target_date:
        return videos
    matched = []
    for v in videos:
        date = v.get('date', '')
        title = v.get('title', '')
        if target_date in date or target_date in title:
            matched.append(v)
    return matched

if __name__ == '__main__':
    # 测试
    print("搜索测试:")
    results = search_videos("AI 大模型 2026", limit=3)
    for r in results:
        print(f"  {normalize_video_info(r)}")
    
    print("\n用户视频列表测试:")
    videos = get_user_videos("285286947", limit=3)
    for v in videos:
        print(f"  {normalize_video_info(v)}")
