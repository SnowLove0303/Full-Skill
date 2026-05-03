#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenCLI Bilibili Video Fetcher - Bypasses API rate limits via Chrome
Uses OpenCLI to get BV numbers, then yt-dlp to get full metadata
"""

import subprocess
import re
import json
import time
import sys
import os
import io
from typing import List, Optional

# Fix stdout encoding for Chinese Windows
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
except:
    pass

def run_cmd(cmd: str, timeout: int = 60) -> str:
    """Run shell command with proper encoding"""
    for enc in ('gbk', 'utf-8', 'cp936'):
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                encoding=enc, errors='replace', timeout=timeout
            )
            return result.stdout + result.stderr
        except Exception:
            continue
    return ""

def fetch_via_opencli(uid: str, target_date: str = None, max_videos: int = 30) -> List[dict]:
    """
    Get UP videos via OpenCLI Chrome takeover
    Strategy: open -> state -> parse BV numbers -> yt-dlp metadata
    """
    print(f" [INFO] OpenCLI fetching: UID={uid}")
    
    # Step 1: Open space page
    space_url = f"https://space.bilibili.com/{uid}/video"
    result = run_cmd(f'opencli operate open "{space_url}"', timeout=30)
    if "error" in result.lower() and "navigated" not in result.lower():
        print(f" [FAIL] OpenCLI open failed")
        return []
    
    time.sleep(2)
    
    # Step 2: Scroll to load more videos
    scroll_times = (max_videos // 20) + 2
    for i in range(scroll_times):
        run_cmd('opencli operate eval "window.scrollBy(0,1000)"', timeout=10)
        time.sleep(1)
        if i == 0:
            print(f" [INFO] Scrolling...")
    
    time.sleep(1)
    
    # Step 3: Get state and extract BV numbers
    state_result = run_cmd('opencli operate state', timeout=20)
    bv_list = _extract_bv_list(state_result)
    
    if not bv_list:
        print(f" [FAIL] No BVs found")
        return []
    
    print(f" [OK] Found {len(bv_list)} BVs, fetching metadata...")
    
    # Step 4: Get metadata via yt-dlp for each BV
    videos = []
    for bv in bv_list[:max_videos]:
        meta = _fetch_metadata_ytmdlp(bv)
        if meta:
            videos.append(meta)
    
    print(f" [OK] Got metadata for {len(videos)} videos")
    return videos

def _extract_bv_list(state_output: str) -> List[str]:
    """Extract BV numbers from opencli state output"""
    seen = set()
    bvs = []
    for match in re.finditer(r'(BV[a-zA-Z0-9]+)', state_output):
        bv = match.group(1)
        if bv not in seen:
            seen.add(bv)
            bvs.append(bv)
    return bvs

def _fetch_metadata_ytmdlp(bvid: str) -> Optional[dict]:
    """Get video metadata via yt-dlp"""
    try:
        cookies_arg = ''
        cookies_file = os.environ.get("BILIBILI_COOKIES_FILE", "")
        if os.path.exists(cookies_file):
            cookies_arg = f'--cookies "{cookies_file}"'
        
        cmd = f'yt-dlp {cookies_arg} --skip-download --print "%(upload_date)s|%(view_count)s|%(duration)s|%(title)s|{bvid}" "https://www.bilibili.com/video/{bvid}" 2>&1'
        result = run_cmd(cmd, timeout=30)
        
        # Parse output
        for line in result.split('\n'):
            line = line.strip()
            if '|' in line and bvid in line:
                parts = line.split('|')
                if len(parts) >= 5:
                    pub_date = parts[0].strip()
                    views = 0
                    try: views = int(parts[1].strip())
                    except: pass
                    duration = 0
                    try: duration = int(float(parts[2].strip()))
                    except: pass
                    title = parts[3].strip()
                    
                    # Extract date from title if not in upload_date
                    title_date = None
                    date_m = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2})', title)
                    if date_m:
                        title_date = date_m.group(1).replace('/', '-')
                    
                    return {
                        'bvid': bvid,
                        'title': title,
                        'pub_date': pub_date if pub_date and pub_date != 'NA' else '',
                        'title_date': title_date,
                        'duration': duration,
                        'views': views,
                        'url': f"https://www.bilibili.com/video/{bvid}",
                    }
    except Exception as e:
        pass
    return None

def fetch_latest_via_opencli(uid: str, target_date: str = None) -> Optional[dict]:
    """Get latest video"""
    videos = fetch_via_opencli(uid, max_videos=30)
    if not videos:
        return None
    
    if target_date:
        for v in videos:
            if target_date in (v.get('title', ''), v.get('pub_date', '')):
                return v
    
    return videos[0]

if __name__ == '__main__':
    uid = sys.argv[1] if len(sys.argv) > 1 else "285286947"
    print(f"Testing: UID={uid}")
    videos = fetch_via_opencli(uid)
    print(f"\nFirst 10 videos:")
    for i, v in enumerate(videos[:10], 1):
        title = v.get('title', '[NO_TITLE]')[:40]
        print(f"{i:2}. {v.get('pub_date', ''):>12} | {v.get('views', 0):>6} | {title} | {v['bvid']}")
