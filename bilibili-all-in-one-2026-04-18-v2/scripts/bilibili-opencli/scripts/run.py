# -*- coding: utf-8 -*-
"""
Bilibili OpenCLI Workflow - 主入口
用法:
  python run.py --search "关键词" --limit 5
  python run.py --uid 285286947 --limit 5
  python run.py --bvid BV11jDnBfErS,BV1FtDEByEKM
  python run.py --search "AI 早报" --date 2026-04-09 --limit 10
"""
import sys
import json
import argparse
import os
from pathlib import Path

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from search import search, get_up_videos
from download import download_batch
from transcribe import transcribe_batch
from formatter import generate_note, generate_daily_summary

DEFAULT_TEMP = os.environ.get("BILIBILI_OUTPUT_DIR", str(Path.home() / "bilibili-ai-news"))
DEFAULT_VAULT = os.environ.get("BILIBILI_VAULT_DIR", str(Path.home() / "Documents" / "Obsidian Vault" / "实时快报"))

def parse_args():
    parser = argparse.ArgumentParser(description='Bilibili OpenCLI Workflow')
    
    # 搜索模式
    parser.add_argument('--search', type=str, help='搜索关键词（与 --uid 二选一）')
    parser.add_argument('--uid', type=str, help='UP主 UID，多个逗号分隔（与 --search 二选一）')
    parser.add_argument('--bvid', type=str, help='直接指定 BV 号，多个逗号分隔')
    
    # 过滤
    parser.add_argument('--limit', type=int, default=5, help='每个来源最多取多少条（默认5）')
    parser.add_argument('--date', type=str, default=None, help='只处理指定日期的视频（YYYY-MM-DD）')
    
    # 路径
    parser.add_argument('--output', type=str, default=DEFAULT_TEMP, help=f'下载目录（默认{DEFAULT_TEMP}）')
    parser.add_argument('--vault', type=str, default=DEFAULT_VAULT, help=f'Obsidian 路径')
    
    # 行为
    parser.add_argument('--dry-run', action='store_true', help='只搜索/列出，不下载不转录')
    parser.add_argument('--skip-download', action='store_true', help='跳过下载')
    parser.add_argument('--skip-transcribe', action='store_true', help='跳过转录')
    parser.add_argument('--parallel', type=int, default=3, help='并行下载数（默认3）')
    parser.add_argument('--engine', type=str, default='whisper', 
                        choices=['whisper', 'funasr', 'auto'],
                        help='转录引擎（默认whisper）')
    
    return parser.parse_args()

def main():
    args = parse_args()
    
    if not args.search and not args.uid and not args.bvid:
        print("错误: 必须指定 --search 或 --uid 或 --bvid")
        sys.exit(1)
    
    print("=" * 60)
    print("  Bilibili OpenCLI Workflow")
    print("=" * 60)
    
    # Step 1: 搜索/获取视频列表
    print("\n[Step 1] 获取视频列表")
    print("-" * 40)
    
    all_videos = []
    
    if args.bvid:
        # 直接指定 BV 号
        bvids = [b.strip() for b in args.bvid.split(',')]
        all_videos = [{'bvid': b, 'title': b, 'source': 'direct'} for b in bvids if b.startswith('BV')]
        print(f"直接指定 {len(all_videos)} 个 BV 号")
    
    elif args.search:
        all_videos = search(args.search, limit=args.limit, date_filter=args.date)
    
    elif args.uid:
        all_videos = get_up_videos(args.uid, limit=args.limit, date_filter=args.date)
    
    if not all_videos:
        print("未获取到任何视频，退出")
        sys.exit(0)
    
    # 过滤无 BV 号的
    all_videos = [v for v in all_videos if v.get('bvid', '').startswith('BV')]
    
    print(f"\n获取到 {len(all_videos)} 个视频:")
    for i, v in enumerate(all_videos, 1):
        date = v.get('date', 'N/A')
        title = v.get('title', v.get('bvid', ''))
        author = v.get('author', '')
        plays = v.get('plays', 0)
        print(f"  {i}. [{date}] {author} - {title[:40]} (播放:{plays})")
    
    if args.dry_run:
        print("\n[Dry Run] 跳过下载和转录")
        return
    
    # Step 2: 下载
    print("\n[Step 2] 批量下载")
    print("-" * 40)
    
    if args.skip_download:
        print("[跳过下载]")
    else:
        results = download_batch(all_videos, output_dir=args.output, parallel=args.parallel)
        # downloaded 包含成功+跳过（已有文件）的bvids
        downloaded_bvids = {r['bvid'] for r in results if r['status'] in ('success', 'skipped', 'cached')}
        if not downloaded_bvids and results:
            # 全部失败了
            print("没有成功下载的视频，退出")
            sys.exit(1)
        # 无论下载成功还是跳过，都从 all_videos 取bvids去转录（音频文件已有）
        print(f"[下载] 完成，可用视频: {len(downloaded_bvids) if downloaded_bvids else len(all_videos)} 个")
    
    # Step 3: 转录
    print("\n[Step 3] 批量转录")
    print("-" * 40)
    
    if args.skip_transcribe:
        print("[跳过转录]")
        transcribed = all_videos
    else:
        bvids_to_transcribe = [v['bvid'] for v in all_videos]
        t_results = transcribe_batch(bvids_to_transcribe, 
                                      output_dir=args.output,
                                      engine=args.engine,
                                      parallel=args.parallel)
        
        transcribed = []
        for v, r in zip(all_videos, t_results):
            if r['status'] in ('success', 'skipped', 'cached'):
                transcribed.append(v)
        
        if not transcribed:
            # 即使转录失败，只要音频存在就尝试生成笔记
            transcribed = [v for v in all_videos if v.get('bvid')]
            print(f"[警告] 无成功转录，但仍有 {len(transcribed)} 个视频可生成笔记")
    
    # Step 4: 生成笔记
    print("\n[Step 4] 生成 Obsidian 笔记")
    print("-" * 40)
    
    note_paths = []
    for v in transcribed:
        bvid = v['bvid']
        path = generate_note(bvid, v, temp_dir=args.output, vault_path=args.vault)
        note_paths.append(path)
        print(f"  [OK] {Path(path).name}")
    
    # Step 5: 生成综合日报（多视频时）
    if len(transcribed) > 1:
        summary_path = generate_daily_summary(transcribed, temp_dir=args.output, vault_path=args.vault)
        if summary_path:
            print(f"  [OK] 综合日报: {Path(summary_path).name}")
    
    print("\n" + "=" * 60)
    print(f"完成！共处理 {len(transcribed)} 个视频")
    print(f"笔记保存在: {args.vault}")
    print("=" * 60)

if __name__ == '__main__':
    main()
