# -*- coding: utf-8 -*-
"""Bilibili search helpers: keyword search, UP videos, and target-video lookup."""
import json
from bilibili_utils import search_videos, get_user_videos, normalize_video_info, match_date


def _norm(value) -> str:
    return str(value or "").casefold().strip()


def _contains(haystack, needle) -> bool:
    needle = _norm(needle)
    return not needle or needle in _norm(haystack)


def _score_video(video: dict, *, title: str | None, author: str | None, date_filter: str | None, must_terms: list[str]) -> int:
    score = 0
    text = " ".join([
        str(video.get("title", "")),
        str(video.get("author", "")),
        str(video.get("bvid", "")),
        str(video.get("date", "")),
    ])
    if author and _contains(video.get("author", ""), author):
        score += 40
    if date_filter and (date_filter in str(video.get("date", "")) or date_filter in str(video.get("title", ""))):
        score += 30
    if title and _contains(video.get("title", ""), title):
        score += 30
    for term in must_terms:
        if _contains(text, term):
            score += 10
    try:
        score += min(int(video.get("plays", 0)) // 100000, 10)
    except Exception:
        pass
    return score


def search(keyword: str, limit=20, date_filter: str | None = None) -> list[dict]:
    """Search Bilibili videos and optionally filter by date."""
    print(f"[Search] keyword: {keyword}")
    results = search_videos(keyword, limit=limit)
    videos = [normalize_video_info(r) for r in results]
    if date_filter:
        videos = match_date(videos, date_filter)
        print(f"[Search] after date filter: {len(videos)}")
    else:
        print(f"[Search] results: {len(videos)}")
    return videos


def find_video(
    query: str,
    *,
    limit=20,
    title: str | None = None,
    author: str | None = None,
    date_filter: str | None = None,
    must_terms: list[str] | None = None,
) -> list[dict]:
    """Use Bilibili site search to locate a specific target video.

    This intentionally starts from station search results, then filters and scores
    candidates so automation can prove the requested video was found.
    """
    must_terms = must_terms or []
    print(f"[Find] Bilibili site search: {query}")
    videos = [normalize_video_info(r) for r in search_videos(query, limit=limit)]
    print(f"[Find] candidates: {len(videos)}")

    filtered = []
    for video in videos:
        if author and not _contains(video.get("author", ""), author):
            continue
        if date_filter and date_filter not in str(video.get("date", "")) and date_filter not in str(video.get("title", "")):
            continue
        if title and not _contains(video.get("title", ""), title):
            continue
        combined = " ".join([
            str(video.get("title", "")),
            str(video.get("author", "")),
            str(video.get("bvid", "")),
            str(video.get("date", "")),
        ])
        if any(not _contains(combined, term) for term in must_terms):
            continue
        video = dict(video)
        video["match_score"] = _score_video(
            video,
            title=title,
            author=author,
            date_filter=date_filter,
            must_terms=must_terms,
        )
        filtered.append(video)

    filtered.sort(key=lambda v: (v.get("match_score", 0), v.get("plays", 0)), reverse=True)
    print(f"[Find] matched: {len(filtered)}")
    return filtered


def get_up_videos(uids: str, limit=20, date_filter: str | None = None) -> list[dict]:
    """Get videos for one or more UP owner UIDs."""
    uid_list = [u.strip() for u in uids.split(",") if u.strip()]
    all_videos = []
    for uid in uid_list:
        print(f"[UP] fetch UID={uid}")
        results = get_user_videos(uid, limit=limit)
        videos = [normalize_video_info(r) for r in results]
        if date_filter:
            before = len(videos)
            videos = match_date(videos, date_filter)
            print(f"[UP] {uid} date filter: {before} -> {len(videos)}")
        else:
            print(f"[UP] {uid} results: {len(videos)}")
        all_videos.extend(videos)
    return all_videos


if __name__ == "__main__":
    for item in find_video(
        "OpenAI OpenClaw AI early news 2026-05-03",
        limit=5,
        author="橘鸦Juya",
        date_filter="2026-05-03",
        must_terms=["OpenClaw"],
    ):
        print(json.dumps(item, ensure_ascii=False))
