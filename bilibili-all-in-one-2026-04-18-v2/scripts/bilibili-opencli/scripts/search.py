# -*- coding: utf-8 -*-
"""搜索模块：关键词搜索 + UP主列表获取"""
import sys
import json
from pathlib import Path
from bilibili_utils import search_videos, get_user_videos, normalize_video_info, match_date

def search(keyword: str, limit=20, date_filter: str = None) -> list[dict]:
    """搜索视频并过滤日期"""
    print(f"[搜索] 关键词: {keyword}")
    results = search_videos(keyword, limit=limit)
    videos = [normalize_video_info(r) for r in results]
    if date_filter:
        videos = match_date(videos, date_filter)
        print(f"[搜索] 日期过滤后剩余: {len(videos)} 条")
    else:
        print(f"[搜索] 获取到: {len(videos)} 条")
    return videos

def get_up_videos(uids: str, limit=20, date_filter: str = None) -> list[dict]:
    """获取一个或多个 UP 主的视频列表"""
    uid_list = [u.strip() for u in uids.split(',')]
    all_videos = []
    for uid in uid_list:
        print(f"[UP主] 获取 UID={uid}")
        results = get_user_videos(uid, limit=limit)
        videos = [normalize_video_info(r) for r in results]
        if date_filter:
            before = len(videos)
            videos = match_date(videos, date_filter)
            print(f"[UP主] {uid} 日期过滤: {before} → {len(videos)} 条")
        else:
            print(f"[UP主] {uid} 获取到: {len(videos)} 条")
        all_videos.extend(videos)
    return all_videos

if __name__ == '__main__':
    # 测试
    v1 = search("AI 早报", limit=3)
    for x in v1:
        print(json.dumps(x, ensure_ascii=False))
    
    v2 = get_up_videos("285286947", limit=3)
    for x in v2:
        print(json.dumps(x, ensure_ascii=False))
