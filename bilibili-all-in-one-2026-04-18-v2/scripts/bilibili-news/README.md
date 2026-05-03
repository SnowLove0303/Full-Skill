# Bilibili AI早报自动生成器

## 快速开始

### 方法 1: 命令行运行

```bash
cd F:\openclaw1\.openclaw\workspace\skills\bilibili-news

# 基本用法 - 获取 UP 主最新视频
python -m bilibili_news 285286947 橘郡Juya

# 指定视频 URL
python -m bilibili_news 285286947 橘郡Juya "https://www.bilibili.com/video/BV1oY9NBCEjR"

# 使用批处理文件
run_ai_news.bat 285286947 橘郡Juya
```

### 方法 2: Python 代码

```python
from bilibili_news import BilibiliNewsGenerator

# 初始化
generator = BilibiliNewsGenerator()

# 生成指定 UP 主的最新视频笔记
result = generator.generate_note(
    up_uid="285286947",      # UP 主 UID
    up_name="橘郡Juya",       # UP 主名称
)
```

## 配置说明

### 默认路径

| 配置 | 默认值 |
|------|--------|
| Obsidian Vault | `C:\Users\chenz\Documents\Obsidian Vault` |
| 临时目录 | `F:\工作区间\ai_news_temp` |
| ffmpeg | `F:\依赖\ffmpeg\ffmpeg-8.1-essentials_build\bin` |
| faster-whisper | `F:\skill\faster-whisper-skill\.venv` |

### 自定义配置

```python
generator = BilibiliNewsGenerator(
    vault_path="D:/MyVault",
    temp_dir="D:/temp",
    ffmpeg_path="D:/ffmpeg/bin",
    whisper_venv="D:/whisper/.venv"
)
```

## 依赖安装

如果 faster-whisper 尚未安装，运行：

```powershell
cd F:\skill\faster-whisper-skill
.\setup.ps1
```

或者手动安装：

```bash
pip install faster-whisper
```

## 工作流程

```
1. 获取视频信息 (yt-dlp)
2. 下载音频 (yt-dlp)
3. 转录音频 (faster-whisper tiny model)
4. 生成 Obsidian 笔记
5. 保存到 实时快报 文件夹
```

## 输出格式

生成的笔记包含：
- Frontmatter (日期、UP主、视频信息、标签)
- 视频信息表格
- 今日要点（待整理）
- 详细内容（从视频描述提取章节）
- 相关链接

## 已知问题

- Bilibili API 可能会限制请求频率
- 如果获取失败，稍后重试
- 确保网络连接稳定

## 示例输出

参见: `C:\Users\chenz\Documents\Obsidian Vault\实时快报\`
