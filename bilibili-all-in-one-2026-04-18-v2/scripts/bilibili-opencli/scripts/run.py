# -*- coding: utf-8 -*-
"""Bilibili OpenCLI workflow entrypoint."""
import argparse
import gc
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from search import find_video, get_up_videos, search
from download import download_batch
from transcribe import release_models, transcribe_batch
from formatter import generate_daily_summary, generate_note

DEFAULT_TEMP = os.environ.get("BILIBILI_OUTPUT_DIR", str(Path.home() / "bilibili-ai-news"))
DEFAULT_VAULT = os.environ.get("BILIBILI_VAULT_DIR", str(Path.home() / "Documents" / "Obsidian Vault" / "实时快报"))


def parse_args():
    parser = argparse.ArgumentParser(description="Bilibili video workflow")

    source = parser.add_argument_group("sources")
    source.add_argument("--search", type=str, help="Keyword search.")
    source.add_argument("--find-video", type=str, help="Use Bilibili site search to locate a specific target video.")
    source.add_argument("--uid", type=str, help="UP owner UID. Multiple UIDs can be separated by commas.")
    source.add_argument("--bvid", type=str, help="Direct BV id. Multiple BV ids can be separated by commas.")

    filters = parser.add_argument_group("filters")
    filters.add_argument("--limit", type=int, default=5, help="Max videos to return/process.")
    filters.add_argument("--date", type=str, default=None, help="Date filter, e.g. 2026-05-03.")
    filters.add_argument("--author", type=str, default=None, help="Author/UP name filter for --find-video.")
    filters.add_argument("--title", type=str, default=None, help="Title substring filter for --find-video.")
    filters.add_argument("--must", action="append", default=[], help="Required term for --find-video. Can be repeated.")
    filters.add_argument("--strict-find", action="store_true", help="Exit non-zero when --find-video has no match.")

    paths = parser.add_argument_group("paths")
    paths.add_argument("--output", type=str, default=DEFAULT_TEMP, help=f"Download/transcript output dir. Default: {DEFAULT_TEMP}")
    paths.add_argument("--vault", type=str, default=DEFAULT_VAULT, help="Obsidian note output dir.")

    behavior = parser.add_argument_group("behavior")
    behavior.add_argument("--dry-run", action="store_true", help="Only list videos; do not download/transcribe.")
    behavior.add_argument("--skip-download", action="store_true", help="Skip download.")
    behavior.add_argument("--skip-transcribe", action="store_true", help="Skip transcription.")
    behavior.add_argument("--parallel", type=int, default=3, help="Download/transcription parallelism.")
    behavior.add_argument("--engine", type=str, default="whisper", choices=["whisper", "funasr", "auto"], help="ASR engine.")
    behavior.add_argument("--keep-cache", action="store_true", help="Keep downloaded media/transcripts after notes are generated.")

    return parser.parse_args()


def _print_video_list(videos: list[dict]) -> None:
    print(f"\nFound {len(videos)} video(s):")
    for i, video in enumerate(videos, 1):
        date = video.get("date", "N/A")
        author = video.get("author", "")
        title = video.get("title", video.get("bvid", ""))
        plays = video.get("plays", 0)
        score = video.get("match_score")
        score_suffix = f" score:{score}" if score is not None else ""
        print(f"  {i}. [{date}] {author} - {title[:80]} ({video.get('bvid', '')}, plays:{plays}{score_suffix})")


def _cleanup_processing_cache(output_dir: str, bvids: list[str]) -> None:
    output_path = Path(output_dir)
    if not output_path.exists():
        return

    suffixes = {".m4a", ".mp4", ".jpg", ".png", ".webp"}
    deleted = 0
    for bvid in bvids:
        candidates = [
            output_path / f"{bvid}_transcript.txt",
            output_path / f"transcript_{bvid}.txt",
        ]
        candidates.extend(path for path in output_path.glob(f"{bvid}*") if path.suffix.lower() in suffixes)
        for path in candidates:
            try:
                if path.exists() and path.is_file():
                    path.unlink()
                    deleted += 1
            except OSError as exc:
                print(f"[Cleanup warn] could not delete {path}: {exc}")

    tmp_dir = output_path / ".tmp"
    try:
        if tmp_dir.exists():
            for path in sorted(tmp_dir.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            tmp_dir.rmdir()
    except OSError as exc:
        print(f"[Cleanup warn] could not delete temp dir {tmp_dir}: {exc}")

    release_models()
    gc.collect()
    print(f"[Cleanup] deleted {deleted} processing cache file(s) and released ASR memory.")


def main():
    args = parse_args()
    if not args.search and not args.find_video and not args.uid and not args.bvid:
        print("Error: specify one of --search, --find-video, --uid, or --bvid.")
        sys.exit(1)

    print("=" * 60)
    print("  Bilibili Workflow")
    print("=" * 60)
    print("\n[Step 1] Resolve video list")
    print("-" * 40)

    all_videos = []
    if args.bvid:
        bvids = [item.strip() for item in args.bvid.split(",") if item.strip().startswith("BV")]
        all_videos = [{"bvid": bvid, "title": bvid, "source": "direct"} for bvid in bvids]
        print(f"[Direct] BV ids: {len(all_videos)}")
    elif args.find_video:
        all_videos = find_video(
            args.find_video,
            limit=args.limit,
            title=args.title,
            author=args.author,
            date_filter=args.date,
            must_terms=args.must,
        )
        if args.strict_find and not all_videos:
            print("[Find] no matching video found.")
            sys.exit(2)
    elif args.search:
        all_videos = search(args.search, limit=args.limit, date_filter=args.date)
    elif args.uid:
        all_videos = get_up_videos(args.uid, limit=args.limit, date_filter=args.date)

    all_videos = [video for video in all_videos if str(video.get("bvid", "")).startswith("BV")]
    if not all_videos:
        print("No videos found.")
        sys.exit(0)

    _print_video_list(all_videos)
    if args.dry_run:
        print("\n[Dry Run] Skip download and transcription.")
        return

    print("\n[Step 2] Download")
    print("-" * 40)
    if args.skip_download:
        print("[Skip] download")
    else:
        results = download_batch(all_videos, output_dir=args.output, parallel=args.parallel)
        downloaded_bvids = {r["bvid"] for r in results if r["status"] in ("success", "skipped", "cached")}
        if not downloaded_bvids and results:
            print("No video/audio download succeeded.")
            sys.exit(1)
        print(f"[Download] available videos: {len(downloaded_bvids) if downloaded_bvids else len(all_videos)}")

    print("\n[Step 3] Transcribe")
    print("-" * 40)
    if args.skip_transcribe:
        print("[Skip] transcription")
        transcribed = all_videos
    else:
        bvids_to_transcribe = [video["bvid"] for video in all_videos]
        t_results = transcribe_batch(
            bvids_to_transcribe,
            output_dir=args.output,
            engine=args.engine,
            parallel=args.parallel,
        )
        transcribed = [
            video
            for video, result in zip(all_videos, t_results)
            if result["status"] in ("success", "skipped", "cached")
        ]
        if not transcribed:
            transcribed = [video for video in all_videos if video.get("bvid")]
            print(f"[Warn] no successful transcript, but {len(transcribed)} videos remain for note generation.")

    print("\n[Step 4] Generate notes")
    print("-" * 40)
    for video in transcribed:
        path = generate_note(video["bvid"], video, temp_dir=args.output, vault_path=args.vault)
        print(f"  [OK] {Path(path).name}")

    if len(transcribed) > 1:
        summary_path = generate_daily_summary(transcribed, temp_dir=args.output, vault_path=args.vault)
        if summary_path:
            print(f"  [OK] summary: {Path(summary_path).name}")

    if args.keep_cache:
        release_models()
        gc.collect()
        print("[Cleanup] --keep-cache set; kept media/transcripts and released ASR memory.")
    else:
        _cleanup_processing_cache(args.output, [video["bvid"] for video in transcribed if video.get("bvid")])

    print("\n" + "=" * 60)
    print(f"Done. Processed {len(transcribed)} video(s).")
    print(f"Notes saved to: {args.vault}")
    print("=" * 60)


if __name__ == "__main__":
    main()
