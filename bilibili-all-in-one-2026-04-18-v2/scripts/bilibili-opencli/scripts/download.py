# -*- coding: utf-8 -*-
"""下载模块：批量下载 + 断点续传 + 并行"""
import sys
import json
import time
import subprocess
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from bilibili_utils import download_video, extract_bvid

def _p(s: str):
    """安全打印（处理 emoji 等非 GBK 字符）"""
    try:
        print(s)
    except UnicodeEncodeError:
        # 替换所有无法编码的字符为 ?
        print(s.encode('gbk', errors='replace').decode('gbk'))

DEFAULT_OUTPUT = os.environ.get("BILIBILI_OUTPUT_DIR", str(Path.home() / "bilibili-ai-news"))

def get_downloaded_bvids(output_dir: Path) -> set[str]:
    """扫描已下载的 BV 号（通过 .m4a 文件）"""
    bvids = set()
    if not output_dir.exists():
        return bvids
    for f in output_dir.iterdir():
        if f.suffix == '.m4a' and f.stem.startswith('BV'):
            # 文件名格式: BV11jDnBfErS_标题.f30280.m4a
            parts = f.stem.split('_')
            if parts:
                bvids.add(parts[0])
    return bvids

def download_single(bvid: str, title: str, output_dir: Path, quality="best") -> dict:
    """下载单个视频，返回结果"""
    result = {
        'bvid': bvid,
        'title': title,
        'status': 'skipped',
        'files': {}
    }
    
    # 检查是否已下载
    m4a_files = list(output_dir.glob(f"{bvid}*.m4a"))
    mp4_files = list(output_dir.glob(f"{bvid}*.mp4"))
    if m4a_files or mp4_files:
        _p(f"[跳过] {bvid} - 已下载")
        result['status'] = 'skipped'
        if m4a_files:
            result['files']['.m4a'] = str(m4a_files[0])
        return result
    
    # 实际下载
    _p(f"[下载] {bvid}...")
    try:
        data = download_video(bvid, str(output_dir), quality=quality)
        # download_video 返回 [{...}] (列表) 或 {'_raw': ...}
        items = data if isinstance(data, list) else []
        item = items[0] if items else {}
        status = item.get('status', '') if isinstance(item, dict) else ''
        if status == 'success':
            result['status'] = 'success'
            # 扫描生成的文件
            for f in output_dir.iterdir():
                if f.stem.startswith(bvid):
                    suffix = f.suffix.lower()
                    if suffix in ('.mp4', '.m4a', '.jpg', '.png', '.webp'):
                        result['files'][suffix] = str(f)
            _p(f"[成功] {bvid} - {item.get('size', '')}")
        else:
            result['status'] = 'failed'
            result['error'] = str(data)
            _p(f"[失败] {bvid} - {result['error'][:100]}")
    except Exception as e:
        result['status'] = 'failed'
        result['error'] = str(e)
        _p(f"[异常] {bvid} - {e}")
    
    return result

def download_batch(videos: list[dict], output_dir: str = DEFAULT_OUTPUT, 
                   parallel: int = 3, skip_existing: bool = True) -> list[dict]:
    """
    批量下载
    
    videos: [{'bvid': 'BVxxx', 'title': '标题', ...}, ...]
    返回: [{'bvid': 'BVxxx', 'status': 'success/skipped/failed', 'files': {...}}, ...]
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    if skip_existing:
        downloaded = get_downloaded_bvids(output_path)
        videos = [v for v in videos if v.get('bvid') and v['bvid'] not in downloaded]
        _p(f"[下载] 跳过已下载，剩余 {len(videos)} 个待下载")
    
    if not videos:
        _p("[下载] 没有需要下载的视频")
        return []
    
    results = []
    
    def do_download(v):
        return download_single(v['bvid'], v.get('title', ''), output_path)
    
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        futures = {pool.submit(do_download, v): v for v in videos}
        for future in as_completed(futures):
            results.append(future.result())
    
    # 统计
    success = sum(1 for r in results if r['status'] == 'success')
    skipped = sum(1 for r in results if r['status'] in ('skipped', 'cached'))
    failed = sum(1 for r in results if r['status'] == 'failed')
    _p(f"\n[下载完成] 成功: {success}  跳过: {skipped}  失败: {failed}")
    
    return results

if __name__ == '__main__':
    # 测试
    test_videos = [
        {'bvid': 'BV11jDnBfErS', 'title': '测试视频'},
    ]
    results = download_batch(test_videos, parallel=1)
    for r in results:
        print(json.dumps(r, ensure_ascii=False))
