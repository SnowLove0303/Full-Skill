# -*- coding: utf-8 -*-
"""Download Bilibili audio/video for transcription."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from bilibili_utils import download_video


DEFAULT_OUTPUT = os.environ.get("BILIBILI_OUTPUT_DIR", str(Path.home() / "bilibili-ai-news"))


def _p(message: str) -> None:
    try:
        print(message)
    except UnicodeEncodeError:
        print(message.encode("gbk", errors="replace").decode("gbk"))


def _scan_downloaded_files(bvid: str, output_dir: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    if not output_dir.exists():
        return files
    for item in output_dir.iterdir():
        if not item.stem.startswith(bvid):
            continue
        suffix = item.suffix.lower()
        if suffix in (".mp4", ".m4a", ".jpg", ".png", ".webp"):
            files[suffix] = str(item)
    return files


def get_downloaded_bvids(output_dir: Path) -> set[str]:
    bvids: set[str] = set()
    if not output_dir.exists():
        return bvids
    for item in output_dir.iterdir():
        if item.suffix.lower() in (".m4a", ".mp4") and item.stem.startswith("BV"):
            bvids.add(item.stem.split("_", 1)[0])
    return bvids


def _download_with_ytdlp(bvid: str, output_dir: Path) -> dict:
    url = f"https://www.bilibili.com/video/{bvid}/"
    output_template = str(output_dir / f"{bvid}_%(title).80s.%(ext)s")
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "-f",
        "ba/bestaudio/best",
        "--no-playlist",
        "-o",
        output_template,
        url,
    ]
    env = os.environ.copy()
    env.setdefault("TEMP", str(output_dir / ".tmp"))
    env.setdefault("TMP", env["TEMP"])
    Path(env["TEMP"]).mkdir(parents=True, exist_ok=True)

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=600,
    )
    files = _scan_downloaded_files(bvid, output_dir)
    if proc.returncode == 0 and files:
        return {"status": "success", "source": "yt-dlp", "files": files}
    return {
        "status": "failed",
        "source": "yt-dlp",
        "files": files,
        "error": (proc.stderr or proc.stdout or "").strip()[-1000:],
        "returncode": proc.returncode,
    }


def download_single(bvid: str, title: str, output_dir: Path, quality: str = "best") -> dict:
    result = {"bvid": bvid, "title": title, "status": "skipped", "files": {}}
    output_dir.mkdir(parents=True, exist_ok=True)

    existing = _scan_downloaded_files(bvid, output_dir)
    if existing:
        _p(f"[skip] {bvid} already downloaded")
        result["status"] = "skipped"
        result["files"] = existing
        return result

    _p(f"[download] {bvid}")
    try:
        data = download_video(bvid, str(output_dir), quality=quality)
        items = data if isinstance(data, list) else []
        item = items[0] if items else {}
        status = item.get("status", "") if isinstance(item, dict) else ""
        if status == "success":
            result["status"] = "success"
            result["files"] = _scan_downloaded_files(bvid, output_dir)
            _p(f"[opencli success] {bvid} {item.get('size', '')}")
            return result

        _p(f"[opencli failed] {bvid}; trying yt-dlp fallback")
        fallback = _download_with_ytdlp(bvid, output_dir)
        result["status"] = fallback["status"]
        result["files"] = fallback.get("files", {})
        if fallback["status"] == "success":
            _p(f"[yt-dlp success] {bvid}")
        else:
            result["error"] = f"{data}\n{fallback.get('error', '')}".strip()
            _p(f"[failed] {bvid} - {result['error'][:120]}")
    except Exception as exc:
        _p(f"[opencli exception] {bvid}; trying yt-dlp fallback: {exc}")
        fallback = _download_with_ytdlp(bvid, output_dir)
        result["status"] = fallback["status"]
        result["files"] = fallback.get("files", {})
        if fallback["status"] == "success":
            _p(f"[yt-dlp success] {bvid}")
        else:
            result["error"] = f"{exc}\n{fallback.get('error', '')}".strip()
            _p(f"[failed] {bvid} - {result['error'][:120]}")
    return result


def download_batch(
    videos: list[dict],
    output_dir: str = DEFAULT_OUTPUT,
    parallel: int = 3,
    skip_existing: bool = True,
) -> list[dict]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if skip_existing:
        downloaded = get_downloaded_bvids(output_path)
        videos = [video for video in videos if video.get("bvid") and video["bvid"] not in downloaded]
        _p(f"[download] remaining after cache check: {len(videos)}")

    if not videos:
        _p("[download] no videos need downloading")
        return []

    results = []

    def do_download(video: dict) -> dict:
        return download_single(video["bvid"], video.get("title", ""), output_path)

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        futures = {pool.submit(do_download, video): video for video in videos}
        for future in as_completed(futures):
            results.append(future.result())

    success = sum(1 for item in results if item["status"] == "success")
    skipped = sum(1 for item in results if item["status"] in ("skipped", "cached"))
    failed = sum(1 for item in results if item["status"] == "failed")
    _p(f"\n[download done] success: {success} skipped: {skipped} failed: {failed}")
    return results


if __name__ == "__main__":
    test_videos = [{"bvid": "BV11jDnBfErS", "title": "test video"}]
    for row in download_batch(test_videos, parallel=1):
        print(json.dumps(row, ensure_ascii=False))
