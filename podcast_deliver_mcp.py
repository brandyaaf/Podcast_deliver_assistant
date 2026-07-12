"""播客交付助手 FastMCP 服务

Tools:
- transcribe_podcast_audio
- generate_titles_and_shownotes
- podcast_deliver_assistant
- save_final_release
"""

import os
import sys
from datetime import date
from pathlib import Path

import yaml
from mcp.server.fastmcp import FastMCP

import transcribe as asr

REPO_ROOT = Path(__file__).resolve().parent
HOST_MD = REPO_ROOT / "host.md"
ARCHIVE_DIR = REPO_ROOT / "archive"
CONFIG_PATH = REPO_ROOT / "config.yaml"
VALID_SHOWS = ("二十而已",)
DEFAULT_SHOW = "二十而已"

mcp = FastMCP("podcast_deliver_assistant")


def load_config() -> dict:
    if not CONFIG_PATH.is_file():
        return {"llm": {"model": "qwen-max", "timeout": 60, "retry_count": 3}, "shows": {}}
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _ensure_api_key() -> str:
    return asr.ensure_api_key()


def get_show_positioning(show_name: str, override: str = "") -> str:
    show_name = show_name.strip() or DEFAULT_SHOW
    if override.strip():
        return override.strip()

    config = load_config()
    show_cfg = (config.get("shows") or {}).get(show_name, {})
    if show_cfg.get("positioning", "").strip():
        return show_cfg["positioning"].strip()

    if HOST_MD.is_file():
        content = HOST_MD.read_text(encoding="utf-8")
        return content.strip()
    return f"节目：{show_name}"


def _build_generation_prompt(transcript: str, show_name: str, positioning: str) -> str:
    return f"""你是播客交付助手，请根据以下转录稿为节目「{show_name}」生成发布文案。

## 节目定位
{positioning}

## 转录稿
{transcript.strip()}

## 输出要求（严格按此结构输出）

### 建议标题（5个）
风格需覆盖：痛点共鸣型 / 认知反差型 / 金句引领型 / 对话感型 / 方法实操型。
每个标题 15-25 字，最后单独一行标注「个人推荐 TOP 1：xxx」。

### Shownotes

#### 导语
20-80 字，以 1-2 个痛点场景开头，留悬念。

#### 时间戳
6-12 条，每条 5-15 字；相邻时间戳间隔至少 3 分钟。
格式：[00:00] 核心内容

#### 互动问题
1 个，引导评论区留言。

#### 金句
3-5 句，必须从转录稿中提取原话，不要编造。
"""


def _call_llm(prompt: str, model: str = None) -> str:
    import dashscope
    from dashscope import Generation

    _ensure_api_key()
    config = load_config()
    llm_cfg = config.get("llm") or {}
    model = model or llm_cfg.get("model", "qwen-max")
    timeout = llm_cfg.get("timeout", 60)

    dashscope.api_key = os.getenv("DASHSCOPE_API_KEY", "")
    base_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/api/v1")
    dashscope.base_http_api_url = base_url

    response = Generation.call(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        result_format="message",
        timeout=timeout,
    )
    if response.status_code != 200:
        raise RuntimeError(f"LLM 调用失败: {response.code} {response.message}")

    content = response.output.choices[0].message.content
    if isinstance(content, list):
        parts = [item.get("text", "") if isinstance(item, dict) else str(item) for item in content]
        return "".join(parts).strip()
    return str(content).strip()


def _normalize_show(show_name: str) -> str:
    name = (show_name or DEFAULT_SHOW).strip()
    if name not in VALID_SHOWS:
        raise ValueError(f"节目名必须是: {', '.join(VALID_SHOWS)}")
    return name


@mcp.tool()
def transcribe_podcast_audio(
    audio_path: str,
    show_name: str = DEFAULT_SHOW,
    title: str = "播客转录",
    archive: bool = True,
) -> str:
    """将播客音频转录为文字（Qwen3-ASR），并可存档到 archive 目录。

    Args:
        audio_path: 本地音频路径（MP3/WAV/M4A 等）
        show_name: 节目名称，演示默认「二十而已」
        title: 节目标题，用于存档文件名
        archive: 是否保存到 archive/<节目名>/
    """
    try:
        show = _normalize_show(show_name)
    except ValueError as e:
        return f"错误：{e}"

    path = Path(audio_path)
    if not path.is_file():
        return f"错误：音频文件不存在 {audio_path}"

    try:
        _ensure_api_key()
        context = f"播客节目：{show}。{get_show_positioning(show)}"
        text = asr.transcribe_sync_local(path, "zh", context)
        if archive:
            out = asr.save_archive(text, show, title)
            return f"转录完成，已存档：{out}\n\n--- 转录稿 ---\n{text}"
        return text
    except Exception as e:
        return f"转录失败：{e}"


@mcp.tool()
def generate_titles_and_shownotes(
    transcript: str,
    show_name: str = DEFAULT_SHOW,
    llm_model: str = "",
    show_positioning: str = "",
) -> str:
    """根据转录稿生成 5 个标题建议与 Shownotes。

    Args:
        transcript: 播客转录文本
        show_name: 节目名称，演示默认「二十而已」
        llm_model: 可选，覆盖 config.yaml 中的 LLM 模型
        show_positioning: 可选，覆盖节目定位
    """
    if not transcript.strip():
        return "错误：请先提供转录文本。"
    try:
        show = _normalize_show(show_name)
        positioning = get_show_positioning(show, show_positioning)
        prompt = _build_generation_prompt(transcript, show, positioning)
        return _call_llm(prompt, llm_model.strip() or None)
    except Exception as e:
        return f"生成失败：{e}"


@mcp.tool()
def podcast_deliver_assistant(
    transcript: str = "",
    audio_path: str = "",
    show_name: str = DEFAULT_SHOW,
    title: str = "播客转录",
    llm_model: str = "",
    show_positioning: str = "",
    archive: bool = True,
) -> str:
    """播客交付助手一站式：音频转录（可选）+ 生成标题与 Shownotes。

    需提供 transcript 或 audio_path 之一；若两者都提供，优先使用 transcript。
    """
    try:
        show = _normalize_show(show_name)
    except ValueError as e:
        return f"错误：{e}"

    text = transcript.strip()
    archive_note = ""

    if not text:
        if not audio_path.strip():
            return "错误：请先上传音频文件或粘贴转录文本。"
        path = Path(audio_path)
        if not path.is_file():
            return f"错误：音频文件不存在 {audio_path}"
        try:
            _ensure_api_key()
            context = f"播客节目：{show}。{get_show_positioning(show, show_positioning)}"
            text = asr.transcribe_sync_local(path, "zh", context)
            if archive:
                out = asr.save_archive(text, show, title)
                archive_note = f"转录稿已存档：{out}\n\n"
        except Exception as e:
            return f"转录失败：{e}"

    try:
        positioning = get_show_positioning(show, show_positioning)
        prompt = _build_generation_prompt(text, show, positioning)
        result = _call_llm(prompt, llm_model.strip() or None)
        return f"{archive_note}{result}"
    except Exception as e:
        return f"生成失败：{e}"


@mcp.tool()
def save_final_release(
    archive_filename: str,
    final_title: str,
    intro: str,
    quotes: str,
    timestamps: str,
    question: str,
    show_name: str = DEFAULT_SHOW,
    rename_if_title_changed: bool = True,
) -> str:
    """将用户确认的最终发布稿追加到 archive 转录文件末尾。"""
    try:
        show = _normalize_show(show_name)
    except ValueError as e:
        return f"错误：{e}"

    file_path = ARCHIVE_DIR / show / archive_filename
    if not file_path.is_file():
        return f"错误：存档文件不存在 {file_path}"

    block = f"""
---

# 最终发布稿

## 标题
{final_title.strip()}

## 导语
{intro.strip()}

## 金句
{quotes.strip()}

## 时间戳
{timestamps.strip()}

## 互动问题
{question.strip()}
"""
    existing = file_path.read_text(encoding="utf-8")
    file_path.write_text(existing.rstrip() + block, encoding="utf-8")

    msg = f"已追加最终发布稿到 {file_path}"
    if rename_if_title_changed:
        stem_title = archive_filename.rsplit("_", 1)[0] if "_" in archive_filename else archive_filename
        if final_title.strip() != stem_title.replace(".txt", ""):
            date_suffix = date.today().strftime("%Y%m%d")
            new_name = f"{asr.sanitize_filename(final_title)}_{date_suffix}.txt"
            new_path = file_path.parent / new_name
            file_path.rename(new_path)
            msg += f"，已重命名为 {new_path.name}"
    return msg


if __name__ == "__main__":
    if "mcp" in sys.modules and hasattr(mcp, "_server"):
        mcp._server.run()
    else:
        mcp.run()
