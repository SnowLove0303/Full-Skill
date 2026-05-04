# Bilibili All-in-One 快速参考

## 常用命令

### 一键安装/检查

```powershell
# 默认安装到 E:\MorenAnzhuangLujing\Huangjingdajian 下的独立目录
.\scripts\setup.ps1 -RunSmokeTest

# 只检查环境
.\scripts\check_env.ps1

# 只跑 smoke test
.\scripts\smoke_test.ps1
```

在 skill 根目录外执行时，使用完整脚本路径：

```powershell
$Skill = "F:\AIAPP\Codex\.codex\skills\bilibili-all-in-one-2026-04-18-v2"
python "$Skill\scripts\bilibili-opencli\scripts\run.py" --search "橘鸦Juya" --limit 3 --dry-run
python "$Skill\scripts\bilibili-opencli\scripts\run.py" --uid 285286947 --limit 3 --dry-run
```

在本仓库内执行时：

```powershell
python .\bilibili-all-in-one-2026-04-18-v2\scripts\bilibili-opencli\scripts\run.py --search "橘鸦Juya" --limit 3 --dry-run
python .\bilibili-all-in-one-2026-04-18-v2\scripts\bilibili-opencli\scripts\run.py --uid 285286947 --limit 3 --dry-run
```

## 可选环境变量

| 变量 | 用途 |
|------|------|
| `OPENCLI_CMD` | 指定 `opencli.cmd` 路径；未设置时自动从 `PATH` 查找。 |
| `BILIBILI_DISABLE_OPENCLI` | 设置为 `1` 时跳过 opencli，直接使用公开 API 兜底。 |
| `ASR_ENGINE` | 转录引擎选择，可按本机环境设为 `funasr` 等。 |
| `BILIBILI_OUTPUT_DIR` | 下载和转录输出目录。 |
| `WHISPER_DOWNLOAD_ROOT` | faster-whisper 模型下载缓存目录。 |
| `WHISPER_MODEL_NAME` | 没有本地模型时自动使用的模型名，默认 `tiny`。 |

## 参数速查

| 需求 | 参数 |
|------|------|
| 搜索关键词 | `--search "关键词"` |
| 指定 UP 主 | `--uid 285286947` |
| 直接指定 BV | `--bvid BVxxxx` |
| 限制数量 | `--limit 3` |
| 只列出不下载 | `--dry-run` |
| 跳过下载 | `--skip-download` |
| 跳过转录 | `--skip-transcribe` |
| 指定日期 | `--date YYYY-MM-DD` |

## 本版优化

- 移除 `opencli` 的硬编码用户路径，优先读取 `OPENCLI_CMD`，其次从 `PATH` 自动发现。
- 搜索无结果或 `opencli` 不可用时，自动使用 Bilibili 公开搜索接口兜底。
- UP 主投稿列表支持 WBI 签名公开接口兜底；如果 Bilibili 风控拦截，仍建议配置 `opencli`。
- 文档路径改为可替换变量和仓库相对路径，避免绑定旧机器目录。

## 注意

- Bilibili 接口可能有频率限制；遇到 `-799` 或 `412` 时稍后重试。
- Windows PowerShell 传中文参数前可先执行 `chcp 65001`；或使用 UID/BV 号避免命令行编码问题。
- 无站内字幕的视频需要下载音频后转录。
- 需要登录或会员清晰度时，应按 `yt-dlp` / `opencli` 的 cookie 机制处理。
