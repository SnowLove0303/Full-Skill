# -*- coding: utf-8 -*-
"""
Bilibili AI早报自动生成器
自动获取 UP 主最新视频，转录并生成 Obsidian 笔记
"""

import os
import sys
import json
import subprocess
import re
from datetime import datetime
from pathlib import Path

# ============== 配置 ==============

# 默认路径配置，可用环境变量覆盖，避免绑定单台机器。
DEFAULT_VAULT_PATH = os.environ.get("BILIBILI_VAULT_ROOT", str(Path.home() / "Documents" / "Obsidian Vault"))
DEFAULT_TEMP_DIR = os.environ.get("BILIBILI_OUTPUT_DIR", str(Path.home() / "bilibili-ai-news"))
DEFAULT_FFMPEG_PATH = os.environ.get("FFMPEG_BIN", "")
DEFAULT_WHISPER_VENV = os.environ.get("WHISPER_VENV", "")
DEFAULT_WHISPER_SCRIPT = os.environ.get("WHISPER_SCRIPT", "")

# ============== 工具函数 ==============

def run_cmd(cmd, env=None, capture=True):
    """执行命令"""
    if env:
        env_copy = os.environ.copy()
        env_copy.update(env)
        env = env_copy
    
    if capture:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True, 
            env=env,
            encoding='utf-8',
            errors='replace'
        )
        return result.returncode == 0, result.stdout, result.stderr
    else:
        result = subprocess.run(cmd, shell=True, env=env)
        return result.returncode == 0, "", ""


def get_video_info(bvid):
    """获取视频信息"""
    cmd = f'yt-dlp --dump-json --no-playlist "https://www.bilibili.com/video/{bvid}"'
    success, stdout, stderr = run_cmd(cmd)
    
    if not success:
        return None
    
    try:
        info = json.loads(stdout)
        return {
            'title': info.get('title', ''),
            'bvid': info.get('id', ''),
            'upload_date': info.get('upload_date', ''),
            'duration': info.get('duration', 0),
            'uploader': info.get('uploader', ''),
            'description': info.get('description', ''),
            'timestamp': info.get('timestamp', 0)
        }
    except json.JSONDecodeError:
        return None


def download_audio(bvid, output_dir, env=None):
    """下载音频"""
    os.makedirs(output_dir, exist_ok=True)
    audio_file = os.path.join(output_dir, "audio.m4a")
    cmd = f'yt-dlp -f "bestaudio" --extract-audio --audio-format m4a -o "{audio_file}" "https://www.bilibili.com/video/{bvid}"'
    success, _, _ = run_cmd(cmd, env=env)
    return success, audio_file if success else None


def transcribe_audio(audio_file, output_file, env=None):
    """转录音频"""
    python_exe = os.path.join(DEFAULT_WHISPER_VENV, "Scripts", "python.exe")
    cmd = f'"{python_exe}" "{DEFAULT_WHISPER_SCRIPT}" "{audio_file}" --language zh --model tiny -o "{output_file}" -f text'
    success, stdout, stderr = run_cmd(cmd, env=env)
    return success


def format_duration(seconds):
    """格式化时长"""
    if not seconds:
        return "未知"
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes}分{secs}秒"


def clean_text(text):
    """清理转录文本中的杂质"""
    if not text:
        return ""
    # 移除一些常见的转录错误模式
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', text)
    # 规范化空白字符
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ============== 笔记生成 ==============

def generate_note_content(video_info, transcript, up_name):
    """生成 Obsidian 笔记内容"""
    
    title = video_info.get('title', '未知标题')
    bvid = video_info.get('bvid', '')
    upload_date = video_info.get('upload_date', '')
    duration = video_info.get('duration', 0)
    description = video_info.get('description', '')
    
    # 格式化日期
    if upload_date:
        formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    else:
        formatted_date = datetime.now().strftime("%Y-%m-%d")
    
    # 清理描述文本，提取时间戳章节
    chapters = []
    if description:
        lines = description.split('\n')
        for line in lines:
            # 匹配时间戳格式 00:09 Google...
            match = re.match(r'(\d{2}:\d{2})\s+(.+)', line.strip())
            if match:
                timestamp = match.group(1)
                content = match.group(2).strip()
                chapters.append((timestamp, content))
    
    # 生成详细内容部分
    content_sections = []
    if chapters:
        for timestamp, content in chapters[:20]:  # 限制前20个章节
            content_sections.append(f"### {timestamp} {content}")
    
    content_text = "\n\n".join(content_sections) if content_sections else "（请查看原视频获取详细内容）"
    
    # 构建笔记
    note = f"""---
date: {formatted_date}
source: Bilibili
up: {up_name}
video: {title}
url: https://www.bilibili.com/video/{bvid}
tags:
  - AI早报
  - 实时快报
---

# {title}

> 日期: {formatted_date}
> UP主: {up_name}
> 原始视频: [{title}](https://www.bilibili.com/video/{bvid})

---

## 视频信息

| 属性 | 值 |
|------|-----|
| 时长 | {format_duration(duration)} |
| BV ID | {bvid} |
| UP主 | {up_name} |

---

## 今日要点

（待整理）

---

## 详细内容

{content_text}

---

## 相关链接

- [原视频](https://www.bilibili.com/video/{bvid})
- [UP主主页](https://space.bilibili.com/{video_info.get('uploader_id', '')})

---

*由 OpenClaw 自动生成于 {datetime.now().strftime('%Y-%m-%d')}*
"""
    
    return note


# ============== 主类 ==============

class BilibiliNewsGenerator:
    """Bilibili AI早报生成器"""
    
    def __init__(self, 
                 vault_path=None,
                 temp_dir=None,
                 ffmpeg_path=None,
                 whisper_venv=None):
        self.vault_path = vault_path or DEFAULT_VAULT_PATH
        self.temp_dir = temp_dir or DEFAULT_TEMP_DIR
        self.ffmpeg_path = ffmpeg_path or DEFAULT_FFMPEG_PATH
        self.whisper_venv = whisper_venv or DEFAULT_WHISPER_VENV
        
        # 创建必要目录
        os.makedirs(self.vault_path, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def get_env(self):
        """获取环境变量"""
        return {
            'PATH': f"{self.ffmpeg_path};{os.environ.get('PATH', '')}",
            'HF_ENDPOINT': 'https://hf-mirror.com'
        }
    
    def get_latest_bvid(self, channel_url):
        """获取用户最新视频 BV"""
        # 使用 yt-dlp 获取用户最新视频
        cmd = f'yt-dlp --dump-json --no-playlist --playlist-end 1 "{channel_url}"'
        success, stdout, _ = run_cmd(cmd, env=self.get_env())
        
        if success and stdout:
            try:
                info = json.loads(stdout)
                return info.get('id', '')
            except json.JSONDecodeError:
                pass
        return None
    
    def generate_note(self, up_uid, up_name, video_url=None, bvid=None):
        """
        生成笔记
        
        Args:
            up_uid: UP 主 UID
            up_name: UP 主名称
            video_url: 视频 URL（可选）
            bvid: 视频 BV ID（可选）
            
        Returns:
            dict: 结果信息
        """
        
        # 确定视频 BV
        if not bvid:
            if video_url:
                # 从 URL 提取 BV
                match = re.search(r'BV[a-zA-Z0-9]+', video_url)
                if match:
                    bvid = match.group(0)
            else:
                # 获取 UP 主最新视频
                channel_url = f"https://space.bilibili.com/{up_uid}"
                bvid = self.get_latest_bvid(channel_url)
        
        if not bvid:
            return {'success': False, 'error': '无法获取视频 BV'}
        
        print(f"[INFO] 处理视频: {bvid}")
        
        # 获取视频信息
        video_info = get_video_info(bvid)
        if not video_info:
            return {'success': False, 'error': '无法获取视频信息'}
        
        print(f"[INFO] 视频标题: {video_info['title']}")
        
        # 检查是否已处理
        upload_date = video_info.get('upload_date', '')
        if upload_date:
            formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
        else:
            formatted_date = datetime.now().strftime("%Y-%m-%d")
        
        output_file = os.path.join(self.vault_path, "实时快报", f"{formatted_date} AI早报.md")
        
        if os.path.exists(output_file):
            print(f"[INFO] 今日已处理: {output_file}")
            return {
                'success': True,
                'skipped': True,
                'output': output_file
            }
        
        # 下载音频
        print("[INFO] 下载音频...")
        success, audio_file = download_audio(bvid, self.temp_dir, env=self.get_env())
        if not success:
            return {'success': False, 'error': '下载音频失败'}
        
        # 转录
        print("[INFO] 转录音频...")
        transcript_file = os.path.join(self.temp_dir, "transcript.txt")
        success = transcribe_audio(audio_file, transcript_file, env=self.get_env())
        if not success:
            return {'success': False, 'error': '转录失败'}
        
        # 读取转录内容
        transcript = ""
        if os.path.exists(transcript_file):
            with open(transcript_file, 'r', encoding='utf-8', errors='replace') as f:
                transcript = clean_text(f.read())
        
        # 生成笔记
        print("[INFO] 生成笔记...")
        note_content = generate_note_content(video_info, transcript, up_name)
        
        # 保存笔记
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(note_content)
        
        # 清理临时文件
        try:
            if os.path.exists(audio_file):
                os.remove(audio_file)
            if os.path.exists(transcript_file):
                os.remove(transcript_file)
        except:
            pass
        
        print(f"[OK] 笔记已保存: {output_file}")
        
        return {
            'success': True,
            'output': output_file,
            'video_info': video_info
        }


# ============== CLI 入口 ==============

def main():
    if len(sys.argv) < 3:
        print("用法: python -m bilibili_news <UP_UID> <UP_NAME> [视频URL]")
        print("示例: python -m bilibili_news 285286947 橘郡Juya")
        sys.exit(1)
    
    up_uid = sys.argv[1]
    up_name = sys.argv[2]
    video_url = sys.argv[3] if len(sys.argv) > 3 else None
    
    generator = BilibiliNewsGenerator()
    result = generator.generate_note(up_uid, up_name, video_url)
    
    if result.get('success'):
        if result.get('skipped'):
            print(f"[SKIP] {result['output']}")
        else:
            print(f"[OK] {result['output']}")
    else:
        print(f"[ERROR] {result.get('error', '未知错误')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
