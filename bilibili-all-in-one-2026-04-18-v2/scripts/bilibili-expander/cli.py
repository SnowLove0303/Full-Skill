# -*- coding: utf-8 -*-
"""Unified CLI for extended Bilibili skill capabilities."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from chrome_cookie import (
    DEFAULT_COOKIE_STATE,
    DEFAULT_ENV_FILE,
    cookie_status,
    export_cookie_from_chrome,
    launch_chrome_for_login,
)
from core import (
    DEFAULT_OUTPUT,
    available_download_backends,
    build_radar_report,
    capture_live_danmaku,
    clean_transcript_text,
    collection_plan,
    create_evidence_pack,
    download_with_backend,
    get_danmaku,
    get_subtitles,
    get_video_info,
    live_room_snapshot,
    load_glossary,
    subscription_check,
    write_json,
)


def print_json(data) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()


def print_json_line(data) -> None:
    text = json.dumps(data, ensure_ascii=False) + "\n"
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()


def cmd_evidence(args: argparse.Namespace) -> int:
    report = create_evidence_pack(
        args.bvid,
        Path(args.output),
        download=args.download,
        backend=args.backend,
        every_seconds=args.every_seconds,
        frame_limit=args.frame_limit,
        lang=args.lang,
    )
    print_json(report)
    return 0


def cmd_danmaku(args: argparse.Namespace) -> int:
    rows = get_danmaku(args.bvid)
    out = Path(args.output) if args.output else DEFAULT_OUTPUT / f"{args.bvid}_danmaku.json"
    write_json(out, rows)
    print_json({"output": str(out), "count": len(rows)})
    return 0


def cmd_subtitle(args: argparse.Namespace) -> int:
    rows = get_subtitles(args.bvid, lang=args.lang)
    out = Path(args.output) if args.output else DEFAULT_OUTPUT / f"{args.bvid}_subtitles.json"
    write_json(out, rows)
    print_json({"output": str(out), "languages": [item.get("lang") for item in rows], "segments": sum(len(item.get("body") or []) for item in rows)})
    return 0


def cmd_download(args: argparse.Namespace) -> int:
    result = download_with_backend(args.bvid, Path(args.output), backend=args.backend)
    print_json(result)
    return 0 if result.get("status") == "success" else 1


def cmd_backends(args: argparse.Namespace) -> int:
    print_json(available_download_backends())
    return 0


def cmd_cookie_status(args: argparse.Namespace) -> int:
    print_json(cookie_status(state_path=Path(args.state), validate=args.validate))
    return 0


def cmd_cookie_from_chrome(args: argparse.Namespace) -> int:
    result = export_cookie_from_chrome(
        cdp_urls=args.cdp_url or None,
        state_path=Path(args.state),
        env_file=Path(args.env_file) if args.persist_env else None,
        wait_login=args.wait_login,
        open_login=args.open_login,
        require_login=args.require_login,
    )
    print_json(result)
    return 0 if result.get("ok") else 1


def cmd_chrome_login(args: argparse.Namespace) -> int:
    launched = launch_chrome_for_login(
        port=args.port,
        profile_dir=Path(args.profile_dir) if args.profile_dir else None,
        chrome_path=args.chrome_path,
    )
    result = export_cookie_from_chrome(
        cdp_urls=[launched["cdp_url"]],
        state_path=Path(args.state),
        env_file=Path(args.env_file) if args.persist_env else None,
        wait_login=args.wait_login,
        open_login=False,
        require_login=True,
    )
    result["chrome"] = launched
    print_json(result)
    return 0 if result.get("ok") else 1


def cmd_radar(args: argparse.Namespace) -> int:
    data = build_radar_report(Path(args.output), keywords=args.keyword or [], rid=args.rid, limit=args.limit)
    print_json({"output": data["output"], "ranking_count": len(data["ranking"]), "keyword_count": len(data["keywords"])})
    return 0


def cmd_subscribe(args: argparse.Namespace) -> int:
    report = subscription_check(
        Path(args.config),
        Path(args.state),
        output=Path(args.output) if args.output else None,
        dry_run=args.dry_run,
    )
    print_json(report)
    return 0


def cmd_live(args: argparse.Namespace) -> int:
    snapshot = live_room_snapshot(args.room_id)
    if args.output:
        write_json(Path(args.output), snapshot)
    print_json(snapshot)
    return 0


def cmd_live_danmaku(args: argparse.Namespace) -> int:
    report = capture_live_danmaku(
        args.room_id,
        Path(args.output),
        seconds=args.seconds,
        max_messages=args.max_messages,
        include_events=args.include_events,
    )
    print_json(report)
    return 0


def cmd_collection(args: argparse.Namespace) -> int:
    data = collection_plan(args.items, Path(args.output))
    print_json({"output": data["output"], "count": data["count"]})
    return 0


def cmd_polish(args: argparse.Namespace) -> int:
    glossary = load_glossary(args.glossary)
    src = Path(args.input)
    dst = Path(args.output) if args.output else src.with_name(src.stem + ".polished" + src.suffix)
    dst.write_text(clean_transcript_text(src.read_text(encoding="utf-8"), glossary), encoding="utf-8")
    print_json({"output": str(dst), "glossary_terms": len(glossary)})
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    print_json(get_video_info(args.bvid))
    return 0


TOOLS = {
    "bilibili.video_info": lambda params: get_video_info(params["bvid"]),
    "bilibili.subtitles": lambda params: get_subtitles(params["bvid"], lang=params.get("lang")),
    "bilibili.danmaku": lambda params: get_danmaku(params["bvid"]),
    "bilibili.live_snapshot": lambda params: live_room_snapshot(params["room_id"]),
    "bilibili.backends": lambda params: available_download_backends(),
}


def cmd_mcp_stdio(args: argparse.Namespace) -> int:
    """Tiny JSON-lines tool server.

    This is intentionally simple and local: each stdin line is
    {"id": "...", "tool": "bilibili.video_info", "params": {...}}.
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        request_id = None
        try:
            request = json.loads(line)
            request_id = request.get("id")
            tool = request.get("tool")
            if tool not in TOOLS:
                raise KeyError(f"unknown tool: {tool}")
            result = TOOLS[tool](request.get("params") or {})
            response = {"id": request_id, "ok": True, "result": result}
        except Exception as exc:
            response = {"id": request_id, "ok": False, "error": str(exc)}
        print_json_line(response)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bilibili all-in-one extended toolkit")
    sub = parser.add_subparsers(dest="command", required=True)

    evidence = sub.add_parser("evidence-pack", help="Create metadata/subtitle/danmaku/keyframe evidence pack")
    evidence.add_argument("--bvid", required=True, help="BV id or video URL")
    evidence.add_argument("--output", default=str(DEFAULT_OUTPUT / "evidence"), help="Evidence output root")
    evidence.add_argument("--download", action="store_true", help="Download media before extracting keyframes")
    evidence.add_argument("--backend", default="auto", choices=["auto", "bbdown", "yutto", "yt-dlp", "yt-dlp-python"], help="Download backend")
    evidence.add_argument("--every-seconds", type=int, default=30, help="Keyframe interval")
    evidence.add_argument("--frame-limit", type=int, default=24, help="Maximum keyframes")
    evidence.add_argument("--lang", default=None, help="Subtitle language filter")
    evidence.set_defaults(func=cmd_evidence)

    danmaku = sub.add_parser("danmaku", help="Fetch danmaku as JSON")
    danmaku.add_argument("--bvid", required=True)
    danmaku.add_argument("--output")
    danmaku.set_defaults(func=cmd_danmaku)

    subtitle = sub.add_parser("subtitle", help="Fetch official subtitles as JSON")
    subtitle.add_argument("--bvid", required=True)
    subtitle.add_argument("--lang")
    subtitle.add_argument("--output")
    subtitle.set_defaults(func=cmd_subtitle)

    download = sub.add_parser("download", help="Download with BBDown/yutto/yt-dlp fallback")
    download.add_argument("--bvid", required=True)
    download.add_argument("--output", default=str(DEFAULT_OUTPUT / "downloads"))
    download.add_argument("--backend", default="auto", choices=["auto", "bbdown", "yutto", "yt-dlp", "yt-dlp-python"])
    download.set_defaults(func=cmd_download)

    backends = sub.add_parser("backends", help="Show available download backends")
    backends.set_defaults(func=cmd_backends)

    cookie_status_parser = sub.add_parser("cookie-status", help="Show masked Bilibili cookie/login status")
    cookie_status_parser.add_argument("--state", default=str(DEFAULT_COOKIE_STATE), help="Cookie state JSON path")
    cookie_status_parser.add_argument("--validate", action=argparse.BooleanOptionalAction, default=True, help="Validate against Bilibili nav API")
    cookie_status_parser.set_defaults(func=cmd_cookie_status)

    cookie_chrome = sub.add_parser("cookie-from-chrome", help="Read Bilibili login cookies from a Chrome DevTools port")
    cookie_chrome.add_argument("--cdp-url", action="append", default=[], help="Chrome DevTools HTTP URL, e.g. http://127.0.0.1:9222")
    cookie_chrome.add_argument("--state", default=str(DEFAULT_COOKIE_STATE), help="Cookie state JSON path")
    cookie_chrome.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="Generated PowerShell env file")
    cookie_chrome.add_argument("--wait-login", type=int, default=180, help="Seconds to wait for QR/login completion")
    cookie_chrome.add_argument("--open-login", action=argparse.BooleanOptionalAction, default=True, help="Open Bilibili login page in Chrome")
    cookie_chrome.add_argument("--require-login", action=argparse.BooleanOptionalAction, default=True, help="Require nav API to report isLogin=true")
    cookie_chrome.add_argument("--persist-env", action=argparse.BooleanOptionalAction, default=True, help="Write .env.generated.ps1 with local cookie env")
    cookie_chrome.set_defaults(func=cmd_cookie_from_chrome)

    chrome_login = sub.add_parser("chrome-login", help="Launch reusable Chrome profile, wait for QR login, then persist Bilibili cookies")
    chrome_login.add_argument("--port", type=int, default=9222, help="Chrome remote debugging port")
    chrome_login.add_argument("--profile-dir", help="Reusable Chrome profile directory")
    chrome_login.add_argument("--chrome-path", help="Chrome or Edge executable path")
    chrome_login.add_argument("--state", default=str(DEFAULT_COOKIE_STATE), help="Cookie state JSON path")
    chrome_login.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="Generated PowerShell env file")
    chrome_login.add_argument("--wait-login", type=int, default=180, help="Seconds to wait for QR/login completion")
    chrome_login.add_argument("--persist-env", action=argparse.BooleanOptionalAction, default=True, help="Write .env.generated.ps1 with local cookie env")
    chrome_login.set_defaults(func=cmd_chrome_login)

    radar = sub.add_parser("radar", help="Create ranking plus keyword radar report")
    radar.add_argument("--keyword", action="append", default=[], help="Keyword to search; can repeat")
    radar.add_argument("--rid", type=int, default=0, help="Bilibili ranking region id")
    radar.add_argument("--limit", type=int, default=10)
    radar.add_argument("--output", default=str(DEFAULT_OUTPUT / f"bilibili-radar.md"))
    radar.set_defaults(func=cmd_radar)

    subscribe = sub.add_parser("subscribe-check", help="Check configured UP owners for new videos")
    subscribe.add_argument("--config", required=True, help="Subscription config JSON")
    subscribe.add_argument("--state", required=True, help="State JSON")
    subscribe.add_argument("--output", help="Markdown report output")
    subscribe.add_argument("--dry-run", action="store_true")
    subscribe.set_defaults(func=cmd_subscribe)

    live = sub.add_parser("live-snapshot", help="Fetch live room status snapshot")
    live.add_argument("--room-id", required=True)
    live.add_argument("--output")
    live.set_defaults(func=cmd_live)

    live_dm = sub.add_parser("live-danmaku", help="Capture live room danmaku via WebSocket")
    live_dm.add_argument("--room-id", required=True)
    live_dm.add_argument("--seconds", type=int, default=60)
    live_dm.add_argument("--max-messages", type=int, default=200)
    live_dm.add_argument("--output", default=str(DEFAULT_OUTPUT / "live-danmaku.jsonl"))
    live_dm.add_argument("--include-events", action="store_true", help="Include gifts/interactions/popularity events")
    live_dm.set_defaults(func=cmd_live_danmaku)

    collection = sub.add_parser("collection-plan", help="Create a processing plan for BV ids or URLs")
    collection.add_argument("items", nargs="+")
    collection.add_argument("--output", default=str(DEFAULT_OUTPUT / "collection-plan.md"))
    collection.set_defaults(func=cmd_collection)

    polish = sub.add_parser("polish-transcript", help="Normalize transcript text and apply glossary replacements")
    polish.add_argument("--input", required=True)
    polish.add_argument("--output")
    polish.add_argument("--glossary", help="JSON dict or [{from,to}] glossary")
    polish.set_defaults(func=cmd_polish)

    info = sub.add_parser("video-info", help="Fetch video metadata")
    info.add_argument("--bvid", required=True)
    info.set_defaults(func=cmd_info)

    mcp = sub.add_parser("mcp-stdio", help="Run a tiny local JSON-lines tool server")
    mcp.set_defaults(func=cmd_mcp_stdio)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
