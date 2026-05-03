# -*- coding: utf-8 -*-
"""转录模块：Whisper（本地路径）+ FunASR（兜底）"""
import sys
import json
import subprocess
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Whisper 本地模型路径（video-news-workflow 同款）
WHISPER_MODEL_SMALL = os.environ.get("WHISPER_MODEL_SMALL", r"F:\AI\whisper_models\faster-whisper-small")
WHISPER_MODEL_MEDIUM = os.environ.get("WHISPER_MODEL_MEDIUM", r"F:\AI\whisper_models\faster-whisper-medium")
FUNASR_VENV = os.environ.get("FUNASR_VENV", r"F:\skill\funasr-skill\.venv")
DEFAULT_OUTPUT = os.environ.get("BILIBILI_OUTPUT_DIR", str(Path.home() / "bilibili-ai-news"))

_wmodel = None
_funasr_model = None


def find_best_whisper_model():
    """选择最好的可用本地模型"""
    if Path(WHISPER_MODEL_MEDIUM).exists():
        return WHISPER_MODEL_MEDIUM
    if Path(WHISPER_MODEL_SMALL).exists():
        return WHISPER_MODEL_SMALL
    return None


def get_whisper_model():
    """全局单例 Whisper 模型"""
    global _wmodel
    if _wmodel is not None:
        return _wmodel
    model_path = find_best_whisper_model()
    if model_path is None:
        raise RuntimeError(f"未找到 Whisper 模型，SMALL={WHISPER_MODEL_SMALL} MEDIUM={WHISPER_MODEL_MEDIUM}")
    from faster_whisper import WhisperModel
    _wmodel = WhisperModel(model_path, device="cpu", compute_type="int8")
    return _wmodel


def get_funasr_model():
    """全局单例 FunASR 模型"""
    global _funasr_model
    if _funasr_model is not None:
        return _funasr_model
    sys.path.insert(0, str(Path(FUNASR_VENV, "Lib", "site-packages")))
    from funasr import AutoModel
    _funasr_model = AutoModel(
        model="iic/SenseVoiceSmall",
        device="cpu",
        disable_update=True
    )
    return _funasr_model


def find_m4a(bvid: str, output_dir: Path) -> Path | None:
    """查找已下载的 m4a 文件"""
    if not output_dir.exists():
        return None
    candidates = list(output_dir.glob(f"{bvid}*.m4a"))
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_mtime)
    return None


def transcribe_whisper(audio_path: str, output_path: str) -> dict:
    """用 Whisper 转录（本地模型）"""
    result = {'engine': 'whisper', 'status': 'pending', 'text': '', 'segments': []}
    try:
        model = get_whisper_model()
        segments, info = model.transcribe(audio_path, language='zh', beam_size=5)
        full_text = []
        seg_list = []
        for seg in segments:
            full_text.append(seg.text)
            seg_list.append({
                'start': round(seg.start, 2),
                'end': round(seg.end, 2),
                'text': seg.text
            })
        text = ''.join(full_text).strip()
        result['text'] = text
        result['segments'] = seg_list
        result['status'] = 'success'
        result['duration'] = round(info.duration, 1) if info.duration else 0
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"[Whisper] {Path(audio_path).name} -> {len(text)} 字, {result['duration']}秒")
    except Exception as e:
        result['status'] = 'failed'
        result['error'] = str(e)
    return result


def transcribe_funasr(audio_path: str, output_path: str) -> dict:
    """用 FunASR SenseVoice 转录"""
    result = {'engine': 'funasr', 'status': 'pending', 'text': '', 'segments': []}
    try:
        model = get_funasr_model()
        res = model.generate(input=audio_path, batch_size_s=300, hotword="")
        text = res[0]['text'].strip() if res else ""
        result['text'] = text
        result['status'] = 'success' if text else 'failed'
        result['duration'] = 0
        if text:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text)
            print(f"[FunASR] {Path(audio_path).name} -> {len(text)} 字")
    except Exception as e:
        result['status'] = 'failed'
        result['error'] = str(e)
    return result


def transcribe(bvid: str, output_dir: str = DEFAULT_OUTPUT, skip_existing=True,
               engine: str = 'auto') -> dict:
    """
    转录单个视频。
    engine='auto': Whisper 优先，失败则 FunASR 兜底
    engine='whisper': 只用 Whisper
    engine='funasr': 只用 FunASR
    skip_existing=True 时跳过已有 txt；False 时强制重转。
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    txt_path = output_dir / f"{bvid}_transcript.txt"
    
    # 找音频文件
    audio_path = find_m4a(bvid, output_dir)
    if audio_path is None:
        return {'bvid': bvid, 'status': 'failed', 'error': f'未找到音频文件 {bvid}*.m4a'}
    
    # 跳过已有的 txt
    if skip_existing and txt_path.exists():
        text = txt_path.read_text(encoding='utf-8')
        return {'bvid': bvid, 'status': 'cached', 'text': text, 'audio': str(audio_path)}
    
    print(f"[转录] {bvid} ({Path(audio_path).name})")
    
    # 根据 engine 参数选择转录策略
    if engine in ('auto', 'whisper'):
        whisper_result = transcribe_whisper(str(audio_path), str(txt_path))
        if whisper_result['status'] == 'success':
            return whisper_result
        if engine == 'whisper':
            return {'bvid': bvid, 'status': 'failed', 'error': whisper_result.get('error', 'Whisper失败')}
        # auto 模式，Whisper 失败则尝试 FunASR
        print(f"[Whisper 失败，切换 FunASR]: {whisper_result.get('error', '')}")
    
    if engine in ('auto', 'funasr'):
        funasr_result = transcribe_funasr(str(audio_path), str(txt_path))
        if funasr_result['status'] == 'success':
            return funasr_result
        return {'bvid': bvid, 'status': 'failed', 'error': funasr_result.get('error', 'FunASR失败')}
    
    return {'bvid': bvid, 'status': 'failed', 'error': '未知引擎: ' + engine}


def transcribe_batch(bvids: list[str], output_dir: str = DEFAULT_OUTPUT, 
                     parallel=1, skip_existing=True,
                     engine: str = 'auto') -> list[dict]:
    """批量转录
    
    engine: 'whisper' | 'funasr' | 'auto'（auto先whisper失败再funasr）
    """
    if parallel <= 1:
        return [transcribe(bvid, output_dir, skip_existing, engine) for bvid in bvids]
    with ThreadPoolExecutor(max_workers=parallel) as ex:
        futures = {ex.submit(transcribe, bvid, output_dir, skip_existing, engine): bvid for bvid in bvids}
        results = []
        for fut in as_completed(futures):
            results.append(fut.result())
        return results
