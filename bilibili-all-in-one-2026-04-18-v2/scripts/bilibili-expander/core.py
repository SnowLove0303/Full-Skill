# -*- coding: utf-8 -*-
"""Extended Bilibili workflows used by the all-in-one skill.

The module intentionally stays dependency-light. Network calls use public web
endpoints and local credentials can be supplied through config files or env vars.
"""

from __future__ import annotations

import html
import json
import os
import re
import base64
import hashlib
import socket
import shutil
import ssl
import struct
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OPENCLI_SCRIPTS = ROOT / "scripts" / "bilibili-opencli" / "scripts"
if str(OPENCLI_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(OPENCLI_SCRIPTS))

from bilibili_utils import extract_bvid, get_user_videos, normalize_video_info, search_videos  # noqa: E402
from chrome_cookie import cookie_value, load_cookie_header, mask_cookie_header  # noqa: E402


DEFAULT_OUTPUT = Path(os.environ.get("BILIBILI_OUTPUT_DIR", str(Path.home() / "bilibili-ai-news")))


@dataclass
class CommandResult:
    backend: str
    returncode: int
    stdout: str
    stderr: str
    command: list[str]

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def safe_name(value: str, fallback: str = "untitled") -> str:
    value = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", value or "").strip(" ._")
    return value[:120] or fallback


def now_slug() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def resolve_bilibili_cookie() -> str:
    try:
        return load_cookie_header()
    except Exception:
        return os.environ.get("BILIBILI_COOKIE", "")


def bilibili_headers(*, referer: str = "https://www.bilibili.com/", accept: str = "application/json,text/plain,*/*") -> dict[str, str]:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": referer,
        "Accept": accept,
    }
    cookie = resolve_bilibili_cookie()
    if cookie:
        headers["Cookie"] = cookie
    return headers


def http_json(url: str, *, referer: str = "https://www.bilibili.com/", timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers=bilibili_headers(referer=referer),
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def http_bytes(url: str, *, referer: str = "https://www.bilibili.com/", timeout: int = 30) -> bytes:
    req = urllib.request.Request(
        url,
        headers=bilibili_headers(referer=referer, accept="*/*"),
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def get_video_info(bvid_or_url: str) -> dict[str, Any]:
    bvid = extract_bvid(bvid_or_url)
    data = http_json(
        f"https://api.bilibili.com/x/web-interface/view?bvid={urllib.parse.quote(bvid)}",
        referer=f"https://www.bilibili.com/video/{bvid}/",
    )
    if data.get("code") != 0:
        raise RuntimeError(f"Bilibili view API failed for {bvid}: {data.get('message')}")
    info = data.get("data") or {}
    owner = info.get("owner") or {}
    stat = info.get("stat") or {}
    pages = info.get("pages") or []
    return {
        "bvid": info.get("bvid") or bvid,
        "aid": info.get("aid"),
        "cid": pages[0].get("cid") if pages else info.get("cid"),
        "title": info.get("title", ""),
        "desc": info.get("desc", ""),
        "pubdate": info.get("pubdate"),
        "date": datetime.fromtimestamp(info.get("pubdate", 0)).strftime("%Y-%m-%d %H:%M:%S") if info.get("pubdate") else "",
        "owner": {"mid": owner.get("mid"), "name": owner.get("name")},
        "stat": {
            "view": stat.get("view", 0),
            "like": stat.get("like", 0),
            "coin": stat.get("coin", 0),
            "favorite": stat.get("favorite", 0),
            "share": stat.get("share", 0),
            "danmaku": stat.get("danmaku", 0),
        },
        "pages": pages,
        "url": f"https://www.bilibili.com/video/{bvid}/",
        "raw": info,
    }


def get_subtitles(bvid_or_url: str, lang: str | None = None) -> list[dict[str, Any]]:
    bvid = extract_bvid(bvid_or_url)
    info = get_video_info(bvid)
    cid = info.get("cid")
    if not cid:
        return []
    data = http_json(
        f"https://api.bilibili.com/x/player/v2?bvid={urllib.parse.quote(bvid)}&cid={cid}",
        referer=f"https://www.bilibili.com/video/{bvid}/",
    )
    subtitles = (((data.get("data") or {}).get("subtitle") or {}).get("subtitles") or [])
    rows: list[dict[str, Any]] = []
    for item in subtitles:
        if lang and lang not in (item.get("lan"), item.get("lan_doc"), item.get("subtitle_url", "")):
            continue
        url = item.get("subtitle_url") or ""
        if url.startswith("//"):
            url = "https:" + url
        if not url:
            continue
        try:
            body = http_json(url, referer=f"https://www.bilibili.com/video/{bvid}/")
        except Exception as exc:
            rows.append({"lang": item.get("lan"), "error": str(exc), "source": url, "body": []})
            continue
        rows.append({
            "lang": item.get("lan"),
            "lang_doc": item.get("lan_doc"),
            "source": url,
            "body": body.get("body") or [],
        })
    return rows


def get_danmaku(bvid_or_url: str) -> list[dict[str, Any]]:
    info = get_video_info(bvid_or_url)
    cid = info.get("cid")
    if not cid:
        return []
    try:
        raw = http_bytes(
            f"https://api.bilibili.com/x/v1/dm/list.so?oid={cid}",
            referer=info["url"],
        ).decode("utf-8", errors="replace").lstrip()
        root = ET.fromstring(raw)
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for node in root.findall("d"):
        parts = (node.attrib.get("p") or "").split(",")
        rows.append({
            "time": float(parts[0]) if len(parts) > 0 and parts[0] else 0.0,
            "mode": int(float(parts[1])) if len(parts) > 1 and parts[1] else 1,
            "size": int(float(parts[2])) if len(parts) > 2 and parts[2] else 25,
            "color": int(float(parts[3])) if len(parts) > 3 and parts[3] else 16777215,
            "timestamp": int(float(parts[4])) if len(parts) > 4 and parts[4] else 0,
            "pool": int(float(parts[5])) if len(parts) > 5 and parts[5] else 0,
            "user_hash": parts[6] if len(parts) > 6 else "",
            "row_id": parts[7] if len(parts) > 7 else "",
            "text": html.unescape(node.text or ""),
        })
    return rows


def seconds_to_ass(value: float) -> str:
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    seconds = value % 60
    return f"{hours:d}:{minutes:02d}:{seconds:05.2f}"


def color_to_ass(value: int) -> str:
    red = value >> 16 & 0xFF
    green = value >> 8 & 0xFF
    blue = value & 0xFF
    return f"&H00{blue:02X}{green:02X}{red:02X}"


def danmaku_to_ass(rows: list[dict[str, Any]], *, width: int = 1920, height: int = 1080) -> str:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,36,&H00FFFFFF,&H000000FF,&H64000000,&H64000000,0,0,0,0,100,100,0,0,1,2,0,8,20,20,24,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    lanes = max(1, height // 48)
    for idx, row in enumerate(rows):
        start = float(row.get("time") or 0)
        end = start + 6
        lane = idx % lanes
        y = 24 + lane * 42
        text = str(row.get("text") or "").replace("\\", "\\\\").replace("{", "(").replace("}", ")")
        color = color_to_ass(int(row.get("color") or 16777215))
        effect = f"{{\\c{color}\\move({width}, {y}, -800, {y})}}"
        lines.append(f"Dialogue: 0,{seconds_to_ass(start)},{seconds_to_ass(end)},Default,,0,0,0,,{effect}{text}\n")
    return "".join(lines)


def run_command(command: list[str], *, timeout: int = 900) -> CommandResult:
    proc = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return CommandResult(
        backend=Path(command[0]).name,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        command=command,
    )


def available_download_backends() -> dict[str, str]:
    backends: dict[str, str] = {}
    for name in ("BBDown", "BBDown.exe", "bbdown", "yutto", "yt-dlp", "yt-dlp.exe"):
        path = shutil.which(name)
        if path:
            key = "bbdown" if "bbdown" in name.casefold() else "yutto" if name == "yutto" else "yt-dlp"
            backends.setdefault(key, path)
    backends.setdefault("yt-dlp-python", sys.executable)
    return backends


def masked_command(command: list[str]) -> list[str]:
    masked = []
    skip_next = False
    for idx, item in enumerate(command):
        if skip_next:
            skip_next = False
            continue
        if item in {"--cookie", "--sessdata", "--sess-data", "--add-header", "-c"} and idx + 1 < len(command):
            masked.append(item)
            next_item = command[idx + 1]
            if item == "--add-header" and next_item.casefold().startswith("cookie:"):
                masked.append("Cookie: " + mask_cookie_header(next_item.split(":", 1)[1].strip()))
            else:
                masked.append(mask_cookie_header(next_item) if item == "--cookie" else "<masked>")
            skip_next = True
        else:
            masked.append(item)
    return masked


def download_with_backend(bvid_or_url: str, output_dir: Path, backend: str = "auto") -> dict[str, Any]:
    bvid = extract_bvid(bvid_or_url)
    output_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://www.bilibili.com/video/{bvid}/"
    backends = available_download_backends()
    cookie = resolve_bilibili_cookie()
    sessdata = cookie_value(cookie, "SESSDATA") if cookie else ""

    order = [backend] if backend != "auto" else ["bbdown", "yutto", "yt-dlp", "yt-dlp-python"]
    attempts = []
    for item in order:
        if item == "bbdown" and backends.get("bbdown"):
            cmd = [backends["bbdown"], url, "--work-dir", str(output_dir)]
            if cookie:
                cmd.extend(["--cookie", cookie])
        elif item == "yutto" and backends.get("yutto"):
            cmd = [backends["yutto"], url, "-d", str(output_dir)]
            if sessdata:
                cmd.extend(["-c", sessdata])
        elif item == "yt-dlp" and backends.get("yt-dlp"):
            cmd = [backends["yt-dlp"], "-f", "ba/bestaudio/best", "--no-playlist", "-o", str(output_dir / f"{bvid}_%(title).80s.%(ext)s"), url]
            if cookie:
                cmd[1:1] = ["--add-header", f"Cookie: {cookie}"]
        elif item == "yt-dlp-python":
            cmd = [sys.executable, "-m", "yt_dlp", "-f", "ba/bestaudio/best", "--no-playlist", "-o", str(output_dir / f"{bvid}_%(title).80s.%(ext)s"), url]
            if cookie:
                cmd[3:3] = ["--add-header", f"Cookie: {cookie}"]
        else:
            continue
        try:
            result = run_command(cmd, timeout=1200)
        except Exception as exc:
            attempts.append({"backend": item, "ok": False, "error": str(exc), "command": masked_command(cmd)})
            continue
        attempts.append({"backend": item, "ok": result.ok, "returncode": result.returncode, "stderr": result.stderr[-1000:], "command": masked_command(cmd)})
        if result.ok:
            return {"status": "success", "bvid": bvid, "backend": item, "used_cookie": bool(cookie), "attempts": attempts}
    return {"status": "failed", "bvid": bvid, "used_cookie": bool(cookie), "attempts": attempts}


def find_local_media(bvid: str, output_dir: Path) -> Path | None:
    if not output_dir.exists():
        return None
    for suffix in (".mp4", ".mkv", ".flv", ".m4a", ".webm"):
        matches = sorted(output_dir.glob(f"{bvid}*{suffix}"))
        if matches:
            return matches[0]
    return None


def extract_keyframes(media_path: Path, frames_dir: Path, *, every_seconds: int = 30, limit: int = 24) -> list[str]:
    if not shutil.which("ffmpeg"):
        return []
    frames_dir.mkdir(parents=True, exist_ok=True)
    output = frames_dir / "frame_%03d.jpg"
    vf = f"fps=1/{max(1, every_seconds)}"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(media_path), "-vf", vf, "-frames:v", str(limit), str(output)]
    result = run_command(cmd, timeout=900)
    if not result.ok:
        return []
    return [str(path) for path in sorted(frames_dir.glob("frame_*.jpg"))]


def clean_transcript_text(text: str, glossary: dict[str, str] | None = None) -> str:
    text = text.replace("\ufeff", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    for src, dst in (glossary or {}).items():
        if src:
            text = text.replace(src, dst)
    return text.strip() + "\n"


def load_glossary(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return {str(k): str(v) for k, v in data.items()}
    if isinstance(data, list):
        return {str(item["from"]): str(item["to"]) for item in data if isinstance(item, dict) and "from" in item and "to" in item}
    return {}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def subtitle_plaintext(subtitles: list[dict[str, Any]]) -> str:
    chunks = []
    for group in subtitles:
        for row in group.get("body") or []:
            content = str(row.get("content") or "").strip()
            if content:
                chunks.append(content)
    return "\n".join(chunks)


def build_sectioned_note(info: dict[str, Any], subtitles: list[dict[str, Any]], danmaku: list[dict[str, Any]], frames: list[str]) -> str:
    title = info.get("title") or info.get("bvid")
    stats = info.get("stat") or {}
    lines = [
        f"# {title}",
        "",
        f"- BV: `{info.get('bvid')}`",
        f"- URL: {info.get('url')}",
        f"- UP: {((info.get('owner') or {}).get('name') or '')}",
        f"- Published: {info.get('date', '')}",
        f"- Views: {stats.get('view', 0)}",
        f"- Likes: {stats.get('like', 0)}",
        f"- Danmaku count: {len(danmaku)}",
        f"- Frames extracted: {len(frames)}",
        "",
        "## Description",
        "",
        info.get("desc", "").strip() or "(empty)",
        "",
        "## Subtitle Text",
        "",
        subtitle_plaintext(subtitles) or "(no subtitle fetched)",
        "",
        "## Danmaku Hot Words",
        "",
    ]
    words: dict[str, int] = {}
    for row in danmaku:
        for token in re.findall(r"[\w\u4e00-\u9fff]{2,}", str(row.get("text") or "")):
            words[token] = words.get(token, 0) + 1
    hot = sorted(words.items(), key=lambda item: item[1], reverse=True)[:30]
    lines.extend([f"- {word}: {count}" for word, count in hot] or ["(no danmaku)"])
    lines.extend(["", "## Keyframes", ""])
    lines.extend([f"- `{Path(frame).name}`" for frame in frames] or ["(no frames extracted)"])
    return "\n".join(lines) + "\n"


def create_evidence_pack(
    bvid_or_url: str,
    output_root: Path,
    *,
    download: bool = False,
    backend: str = "auto",
    every_seconds: int = 30,
    frame_limit: int = 24,
    lang: str | None = None,
) -> dict[str, Any]:
    info = get_video_info(bvid_or_url)
    bvid = info["bvid"]
    pack_dir = output_root / f"{bvid}-{safe_name(info.get('title', ''), bvid)}"
    pack_dir.mkdir(parents=True, exist_ok=True)
    media_dir = pack_dir / "media"

    download_result = None
    if download:
        download_result = download_with_backend(bvid, media_dir, backend=backend)

    subtitles = get_subtitles(bvid, lang=lang)
    danmaku = get_danmaku(bvid)
    write_json(pack_dir / "metadata.json", info)
    write_json(pack_dir / "subtitles.json", subtitles)
    write_json(pack_dir / "danmaku.json", danmaku)
    write_markdown(pack_dir / "danmaku.ass", danmaku_to_ass(danmaku))

    media_path = find_local_media(bvid, media_dir) or find_local_media(bvid, output_root) or find_local_media(bvid, DEFAULT_OUTPUT)
    frames = extract_keyframes(media_path, pack_dir / "frames", every_seconds=every_seconds, limit=frame_limit) if media_path else []
    write_markdown(pack_dir / "sectioned.md", build_sectioned_note(info, subtitles, danmaku, frames))

    report = {
        "status": "ok",
        "pack_dir": str(pack_dir),
        "bvid": bvid,
        "has_subtitle": any(item.get("body") for item in subtitles),
        "danmaku_count": len(danmaku),
        "frames_count": len(frames),
        "download": download_result,
        "media_path": str(media_path) if media_path else None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(pack_dir / "smoke-report.json", report)
    return report


def ranking_videos(rid: int = 0, day: int = 3) -> list[dict[str, Any]]:
    url = f"https://api.bilibili.com/x/web-interface/ranking/v2?rid={rid}&type=all"
    try:
        data = http_json(url)
    except Exception:
        data = {}
    rows = []
    for rank, item in enumerate((data.get("data") or {}).get("list") or [], 1):
        owner = item.get("owner") or {}
        stat = item.get("stat") or {}
        rows.append({
            "rank": rank,
            "bvid": item.get("bvid"),
            "title": item.get("title"),
            "author": owner.get("name"),
            "plays": stat.get("view", 0),
            "likes": stat.get("like", 0),
            "url": f"https://www.bilibili.com/video/{item.get('bvid')}/",
            "source": f"ranking-rid-{rid}-day-{day}",
        })
    if rows:
        return rows

    try:
        popular = http_json("https://api.bilibili.com/x/web-interface/popular?ps=20&pn=1")
    except Exception:
        return rows
    for rank, item in enumerate((popular.get("data") or {}).get("list") or [], 1):
        owner = item.get("owner") or {}
        stat = item.get("stat") or {}
        rows.append({
            "rank": rank,
            "bvid": item.get("bvid"),
            "title": item.get("title"),
            "author": owner.get("name"),
            "plays": stat.get("view", 0),
            "likes": stat.get("like", 0),
            "url": f"https://www.bilibili.com/video/{item.get('bvid')}/",
            "source": "popular-fallback",
        })
    return rows


def build_radar_report(output: Path, *, keywords: list[str], rid: int = 0, limit: int = 10) -> dict[str, Any]:
    ranking = ranking_videos(rid=rid)[:limit]
    keyword_results = {}
    for keyword in keywords:
        keyword_results[keyword] = [normalize_video_info(item) for item in search_videos(keyword, limit=limit)]
    lines = ["# Bilibili Content Radar", "", f"- Created: {datetime.now().isoformat(timespec='seconds')}", f"- Ranking rid: {rid}", ""]
    lines.extend(["## Ranking", ""])
    for item in ranking:
        lines.append(f"{item['rank']}. [{item['title']}]({item['url']}) - {item.get('author', '')} / {item.get('plays', 0)} views")
    for keyword, videos in keyword_results.items():
        lines.extend(["", f"## Keyword: {keyword}", ""])
        for idx, item in enumerate(videos, 1):
            lines.append(f"{idx}. [{item.get('title', '')}]({item.get('url', '')}) - {item.get('author', '')} / {item.get('plays', 0)} views")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    data = {"output": str(output), "ranking": ranking, "keywords": keyword_results}
    write_json(output.with_suffix(".json"), data)
    return data


def subscription_check(config_path: Path, state_path: Path, output: Path | None = None, *, dry_run: bool = False) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"seen": {}}
    users = config.get("users") or []
    limit = int(config.get("limit", 10))
    new_items = []
    for user in users:
        uid = str(user.get("uid") if isinstance(user, dict) else user)
        label = str(user.get("name") if isinstance(user, dict) else uid)
        seen = set(state.setdefault("seen", {}).setdefault(uid, []))
        videos = [normalize_video_info(item) for item in get_user_videos(uid, limit=limit)]
        for video in videos:
            bvid = video.get("bvid")
            if bvid and bvid not in seen:
                video["subscription"] = {"uid": uid, "name": label}
                new_items.append(video)
                seen.add(bvid)
        state["seen"][uid] = sorted(seen)
    report = {"new_count": len(new_items), "new_items": new_items, "checked_at": datetime.now().isoformat(timespec="seconds")}
    if output:
        lines = ["# Bilibili Subscription Monitor", "", f"- New videos: {len(new_items)}", ""]
        for item in new_items:
            sub = item.get("subscription") or {}
            lines.append(f"- [{item.get('title', '')}]({item.get('url', '')}) - {sub.get('name', '')} / `{item.get('bvid')}`")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if not dry_run:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def live_room_snapshot(room_id: str) -> dict[str, Any]:
    data = http_json(f"https://api.live.bilibili.com/room/v1/Room/get_info?room_id={urllib.parse.quote(str(room_id))}")
    if data.get("code") != 0:
        raise RuntimeError(f"Live room API failed: {data.get('message')}")
    info = data.get("data") or {}
    return {
        "room_id": info.get("room_id") or room_id,
        "short_id": info.get("short_id"),
        "title": info.get("title"),
        "live_status": info.get("live_status"),
        "online": info.get("online"),
        "area_name": info.get("area_name"),
        "parent_area_name": info.get("parent_area_name"),
        "tags": info.get("tags"),
        "url": f"https://live.bilibili.com/{room_id}",
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "raw": info,
    }


def live_danmaku_info(room_id: str) -> dict[str, Any]:
    referer = f"https://live.bilibili.com/{room_id}"
    data = http_json(
        f"https://api.live.bilibili.com/xlive/web-room/v1/index/getDanmuInfo?id={urllib.parse.quote(str(room_id))}&type=0",
        referer=referer,
    )
    if data.get("code") != 0:
        # getDanmuInfo can be protected by Bilibili risk control for anonymous
        # callers. The older room/v1 endpoint still returns the same token and
        # host list without account credentials.
        data = http_json(
            f"https://api.live.bilibili.com/room/v1/danmu/getConf?room_id={urllib.parse.quote(str(room_id))}&platform=pc&player=web",
            referer=referer,
        )
    if data.get("code") != 0:
        raise RuntimeError(f"Live danmaku info API failed: {data.get('message')}")
    payload = data.get("data") or {}
    hosts = payload.get("host_list") or payload.get("host_server_list") or []
    return {
        "token": payload.get("token") or "",
        "hosts": hosts,
        "raw": payload,
    }


def resolve_live_room_id(room_id: str) -> str:
    snapshot = live_room_snapshot(room_id)
    return str(snapshot.get("room_id") or room_id)


class RawWebSocket:
    """Small binary WebSocket client for Bilibili live danmaku.

    The skill keeps this dependency-free so it works in fresh Codex installs.
    It implements only what the live message stream needs: TLS handshake,
    masked client binary frames, server binary/text frames, ping/pong and close.
    """

    def __init__(self, host: str, port: int = 443, path: str = "/sub", timeout: int = 15) -> None:
        self.host = host
        self.port = port
        self.path = path
        self.timeout = timeout
        self.sock: ssl.SSLSocket | None = None

    def connect(self) -> None:
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        raw = socket.create_connection((self.host, self.port), timeout=self.timeout)
        wrapped = ssl.create_default_context().wrap_socket(raw, server_hostname=self.host)
        wrapped.settimeout(self.timeout)
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "User-Agent: Mozilla/5.0\r\n"
            "\r\n"
        )
        wrapped.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = wrapped.recv(4096)
            if not chunk:
                break
            response += chunk
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError(f"WebSocket handshake failed: {response[:200]!r}")
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest())
        if accept not in response:
            raise RuntimeError("WebSocket handshake failed: invalid accept header")
        self.sock = wrapped

    def close(self) -> None:
        if not self.sock:
            return
        try:
            self.send_frame(b"", opcode=0x8)
        except Exception:
            pass
        try:
            self.sock.close()
        finally:
            self.sock = None

    def send_binary(self, payload: bytes) -> None:
        self.send_frame(payload, opcode=0x2)

    def send_frame(self, payload: bytes, opcode: int) -> None:
        if not self.sock:
            raise RuntimeError("WebSocket is not connected")
        first = 0x80 | opcode
        length = len(payload)
        mask_bit = 0x80
        if length < 126:
            header = struct.pack("!BB", first, mask_bit | length)
        elif length < 65536:
            header = struct.pack("!BBH", first, mask_bit | 126, length)
        else:
            header = struct.pack("!BBQ", first, mask_bit | 127, length)
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[idx % 4] for idx, byte in enumerate(payload))
        self.sock.sendall(header + mask + masked)

    def recv_frame(self, timeout: int | None = None) -> tuple[int, bytes]:
        if not self.sock:
            raise RuntimeError("WebSocket is not connected")
        old_timeout = self.sock.gettimeout()
        if timeout is not None:
            self.sock.settimeout(timeout)
        try:
            header = self._recv_exact(2)
            first, second = header
            opcode = first & 0x0F
            length = second & 0x7F
            masked = bool(second & 0x80)
            if length == 126:
                length = struct.unpack("!H", self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._recv_exact(8))[0]
            mask = self._recv_exact(4) if masked else b""
            payload = self._recv_exact(length) if length else b""
            if masked:
                payload = bytes(byte ^ mask[idx % 4] for idx, byte in enumerate(payload))
            if opcode == 0x9:
                self.send_frame(payload, opcode=0xA)
                return self.recv_frame(timeout=timeout)
            if opcode == 0x8:
                raise RuntimeError("WebSocket closed by server")
            return opcode, payload
        finally:
            if timeout is not None:
                self.sock.settimeout(old_timeout)

    def _recv_exact(self, size: int) -> bytes:
        if not self.sock:
            raise RuntimeError("WebSocket is not connected")
        chunks = []
        remaining = size
        while remaining:
            chunk = self.sock.recv(remaining)
            if not chunk:
                raise RuntimeError("WebSocket connection ended unexpectedly")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)


def build_live_packet(operation: int, body: bytes | dict[str, Any], *, version: int = 1, sequence: int = 1) -> bytes:
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8") if isinstance(body, dict) else body
    packet_len = 16 + len(payload)
    return struct.pack("!IHHII", packet_len, 16, version, operation, sequence) + payload


def parse_live_packets(payload: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while offset + 16 <= len(payload):
        packet_len, header_len, version, operation, sequence = struct.unpack("!IHHII", payload[offset : offset + 16])
        if packet_len <= 0 or offset + packet_len > len(payload):
            break
        body = payload[offset + header_len : offset + packet_len]
        offset += packet_len
        if operation == 3:
            popularity = struct.unpack("!I", body[-4:])[0] if len(body) >= 4 else None
            rows.append({"cmd": "POPULARITY", "popularity": popularity, "sequence": sequence})
            continue
        if operation != 5:
            continue
        if version == 2:
            try:
                import zlib

                rows.extend(parse_live_packets(zlib.decompress(body)))
            except Exception as exc:
                rows.append({"cmd": "DECOMPRESS_ERROR", "error": str(exc)})
            continue
        if version == 3:
            try:
                import brotli  # type: ignore

                rows.extend(parse_live_packets(brotli.decompress(body)))
            except Exception as exc:
                rows.append({"cmd": "DECOMPRESS_ERROR", "error": str(exc)})
            continue
        try:
            rows.append(json.loads(body.decode("utf-8", errors="replace")))
        except json.JSONDecodeError:
            rows.append({"cmd": "RAW", "text": body.decode("utf-8", errors="replace")})
    return rows


def simplify_live_event(event: dict[str, Any]) -> dict[str, Any]:
    cmd = str(event.get("cmd") or "").split(":", 1)[0]
    now = datetime.now().isoformat(timespec="seconds")
    if cmd == "DANMU_MSG":
        info = event.get("info") or []
        user = info[2] if len(info) > 2 and isinstance(info[2], list) else []
        return {
            "type": "danmaku",
            "time": now,
            "username": user[1] if len(user) > 1 else "",
            "uid": user[0] if user else None,
            "text": info[1] if len(info) > 1 else "",
            "raw_cmd": event.get("cmd"),
        }
    if cmd in {"SEND_GIFT", "COMBO_SEND"}:
        data = event.get("data") or {}
        return {
            "type": "gift",
            "time": now,
            "username": data.get("uname"),
            "uid": data.get("uid"),
            "gift": data.get("giftName") or data.get("gift_name"),
            "num": data.get("num"),
            "raw_cmd": event.get("cmd"),
        }
    if cmd == "INTERACT_WORD":
        data = event.get("data") or {}
        return {
            "type": "interact",
            "time": now,
            "username": data.get("uname"),
            "uid": data.get("uid"),
            "text": data.get("msg_type"),
            "raw_cmd": event.get("cmd"),
        }
    if event.get("cmd") == "POPULARITY":
        return {"type": "popularity", "time": now, "popularity": event.get("popularity"), "raw_cmd": "POPULARITY"}
    return {"type": "event", "time": now, "raw_cmd": event.get("cmd"), "raw": event}


def capture_live_danmaku(
    room_id: str,
    output: Path,
    *,
    seconds: int = 60,
    max_messages: int = 200,
    include_events: bool = False,
) -> dict[str, Any]:
    real_room_id = resolve_live_room_id(room_id)
    server = live_danmaku_info(real_room_id)
    host_rows = server.get("hosts") or []
    if not host_rows:
        raise RuntimeError("No Bilibili live danmaku host returned")
    host_info = host_rows[0]
    host = host_info.get("host") or "broadcastlv.chat.bilibili.com"
    port = int(host_info.get("wss_port") or 443)
    token = server.get("token") or ""
    join_body = {
        "uid": 0,
        "roomid": int(real_room_id),
        "protover": 2,
        "platform": "web",
        "type": 2,
        "key": token,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    markdown_path = output.with_suffix(".md")
    events: list[dict[str, Any]] = []
    started = time.monotonic()
    last_heartbeat = 0.0
    ws = RawWebSocket(host=host, port=port)
    try:
        ws.connect()
        ws.send_binary(build_live_packet(7, join_body, version=1))
        with output.open("w", encoding="utf-8") as handle:
            while time.monotonic() - started < max(1, seconds) and len(events) < max_messages:
                if time.monotonic() - last_heartbeat >= 25:
                    ws.send_binary(build_live_packet(2, b"", version=1))
                    last_heartbeat = time.monotonic()
                try:
                    opcode, payload = ws.recv_frame(timeout=3)
                except socket.timeout:
                    continue
                if opcode not in (0x1, 0x2):
                    continue
                for event in parse_live_packets(payload):
                    simplified = simplify_live_event(event)
                    if simplified["type"] != "danmaku" and not include_events:
                        continue
                    events.append(simplified)
                    handle.write(json.dumps(simplified, ensure_ascii=False) + "\n")
                    if len(events) >= max_messages:
                        break
    finally:
        ws.close()

    lines = [
        "# Bilibili Live Danmaku Capture",
        "",
        f"- Room: {real_room_id}",
        f"- Source: https://live.bilibili.com/{room_id}",
        f"- Host: {host}:{port}",
        f"- Duration seconds: {seconds}",
        f"- Captured: {len(events)}",
        "",
        "## Messages",
        "",
    ]
    for item in events[:100]:
        if item.get("type") == "danmaku":
            lines.append(f"- {item.get('time')} {item.get('username')}: {item.get('text')}")
        else:
            lines.append(f"- {item.get('time')} [{item.get('type')}] {item.get('raw_cmd')}")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "room_id": real_room_id,
        "output": str(output),
        "markdown": str(markdown_path),
        "count": len(events),
        "host": host,
        "duration_seconds": seconds,
    }


def collection_plan(items: list[str], output: Path) -> dict[str, Any]:
    rows = []
    for item in items:
        try:
            rows.append(get_video_info(item))
        except Exception as exc:
            rows.append({"input": item, "error": str(exc)})
    lines = ["# Bilibili Collection Plan", ""]
    for idx, row in enumerate(rows, 1):
        if row.get("error"):
            lines.append(f"{idx}. `{row.get('input')}` - ERROR: {row.get('error')}")
        else:
            lines.append(f"{idx}. [{row.get('title')}]({row.get('url')}) - `{row.get('bvid')}`")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(output.with_suffix(".json"), rows)
    return {"output": str(output), "count": len(rows), "items": rows}
