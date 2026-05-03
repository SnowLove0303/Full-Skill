# -*- coding: utf-8 -*-
"""笔记格式化模块：从转录文本生成 Obsidian 笔记"""
import sys
import json
import re
import os
from pathlib import Path
from datetime import date

VAULT_PATH = os.environ.get("BILIBILI_VAULT_DIR", str(Path.home() / "Documents" / "Obsidian Vault" / "实时快报"))
DEFAULT_TEMP = os.environ.get("BILIBILI_OUTPUT_DIR", str(Path.home() / "bilibili-ai-news"))

def read_transcript(bvid: str, temp_dir: str = DEFAULT_TEMP) -> str:
    """读取转录文本"""
    path = Path(temp_dir) / f"transcript_{bvid}.txt"
    if path.exists():
        return path.read_text(encoding='utf-8')
    return ""

def parse_transcript_text(text: str) -> list[dict]:
    """
    解析转录文本为段落
    简单策略：按句子/段落分割
    """
    if not text:
        return []
    # 简单分句
    paragraphs = []
    current = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            if current:
                paragraphs.append(' '.join(current))
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append(' '.join(current))
    return [{'text': p} for p in paragraphs if p]

def format_content(text: str, title: str, bvid: str, author: str = '', 
                    date_str: str = None, plays: int = 0) -> str:
    """生成格式化笔记"""
    today = date_str or date.today().isoformat()
    
    # YAML frontmatter
    fm = f"""---
date: {today}
source: bilibili
bvid: {bvid}
author: {author}
plays: {plays}
created: {today}
tags:
  - AI早报
  - Bilibili
---

# {title}

> 来源: [{author}](https://www.bilibili.com/video/{bvid}) | 播放: {plays} | 日期: {today}

## 视频内容

"""
    # 内容段落
    paras = parse_transcript_text(text)
    content_parts = []
    for i, p in enumerate(paras[:50]):  # 最多50段
        content_parts.append(f"{p['text']}")
    
    content = '\n\n'.join(content_parts)
    
    # 结语
    footer = f"""

---

_由 OpenCLI Bilibili Workflow 自动生成 | BV: {bvid}_
"""
    
    return fm + content + footer

def beautify_text(text: str) -> str:
    """简单美化：中文-英文间距、标点修正"""
    # 中英文之间加空格
    text = re.sub(r'([\u4e00-\u9fff])([A-Za-z])', r'\1 \2', text)
    text = re.sub(r'([A-Za-z])([\u4e00-\u9fff])', r'\1 \2', text)
    # 数字和中文之间
    text = re.sub(r'([\u4e00-\u9fff])([0-9])', r'\1 \2', text)
    text = re.sub(r'([0-9])([\u4e00-\u9fff])', r'\1 \2', text)
    # 连续空行压缩
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text

def generate_note(bvid: str, video_info: dict, temp_dir: str = DEFAULT_TEMP,
                   vault_path: str = VAULT_PATH) -> str:
    """生成单个视频的 Obsidian 笔记"""
    text = read_transcript(bvid, temp_dir)
    text = beautify_text(text)
    
    title = video_info.get('title', f'视频 {bvid}')
    author = video_info.get('author', video_info.get('up', ''))
    date_str = video_info.get('date', date.today().isoformat())
    plays = video_info.get('plays', 0)
    
    content = format_content(text, title, bvid, author, date_str, plays)
    
    # 保存
    vault = Path(vault_path)
    vault.mkdir(parents=True, exist_ok=True)
    
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)[:50]
    out_file = vault / f"{date_str} AI早报-{safe_title}.md"
    out_file.write_text(content, encoding='utf-8')
    
    return str(out_file)

def generate_daily_summary(videos: list[dict], temp_dir: str = DEFAULT_TEMP,
                            vault_path: str = VAULT_PATH) -> str:
    """生成综合日报（多视频合并）"""
    today = date.today().isoformat()
    all_texts = []
    
    for v in videos:
        bvid = v.get('bvid', '')
        text = read_transcript(bvid, temp_dir)
        if text:
            all_texts.append({
                'bvid': bvid,
                'title': v.get('title', bvid),
                'author': v.get('author', ''),
                'date': v.get('date', today),
                'text': text[:2000]  # 每视频最多取2000字
            })
    
    if not all_texts:
        return None
    
    content_parts = [f"""---
date: {today}
source: bilibili
type: 综合日报
tags:
  - AI早报
  - 综合
---

# AI 早报 · {today}

> {len(all_texts)} 个来源综合 | 自动生成
"""]
    
    for item in all_texts:
        content_parts.append(f"\n## {item['author']} | {item['title']}\n")
        content_parts.append(f"\n{item['text']}\n")
    
    content_parts.append(f"\n_自动生成 | {today}_\n")
    
    content = beautify_text(''.join(content_parts))
    
    vault = Path(vault_path)
    vault.mkdir(parents=True, exist_ok=True)
    out_file = vault / f"{today} AI早报-综合.md"
    out_file.write_text(content, encoding='utf-8')
    
    return str(out_file)

if __name__ == '__main__':
    # 测试
    test_video = {
        'bvid': 'BV11jDnBfErS',
        'title': 'Meta 发布 Muse Spark 模型【AI 早报 2026-04-09】',
        'author': '橘郡Juya',
        'date': '2026-04-09',
        'plays': 16337
    }
    path = generate_note(**test_video)
    print(f"笔记生成: {path}")
