"""Qwen3-ASR 播客转录（DashScope）。"""
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
ARCHIVE_DIR = REPO_ROOT / "archive"
VALID_SHOWS = ("二十而已",)


def load_env_file(env_path: Path) -> None:
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def ensure_api_key() -> str:
    load_env_file(REPO_ROOT / ".env")
    key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "未设置 DASHSCOPE_API_KEY，请复制 .env.example 为 .env 并填入密钥"
        )
    return key


def configure_dashscope():
    import dashscope

    base_url = os.getenv(
        "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/api/v1"
    )
    dashscope.base_http_api_url = base_url
    dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
    return dashscope


def extract_text_from_response(response) -> str:
    if getattr(response, "status_code", None) not in (200, None):
        code = getattr(response, "code", response.status_code)
        msg = getattr(response, "message", str(response))
        raise RuntimeError(f"ASR 请求失败: {code} {msg}")

    output = getattr(response, "output", None)
    if output is None and hasattr(response, "get"):
        output = response.get("output")
    if output is None:
        raise RuntimeError(f"无法解析 ASR 响应: {response}")

    choices = getattr(output, "choices", None) or output.get("choices", [])
    if not choices:
        raise RuntimeError(f"ASR 响应无 choices: {response}")

    choice = choices[0]
    message = getattr(choice, "message", None) or choice.get("message", {})
    content = getattr(message, "content", None) or message.get("content", [])

    parts = []
    for item in content:
        if isinstance(item, dict):
            if item.get("text"):
                parts.append(item["text"])
            elif item.get("transcript"):
                parts.append(item["transcript"])
        elif isinstance(item, str):
            parts.append(item)

    text = "".join(parts).strip()
    if not text:
        raise RuntimeError(f"ASR 返回空文本: {response}")
    return text


def transcribe_sync_local(audio_path: Path, language: str, context: str) -> str:
    dashscope = configure_dashscope()
    from dashscope import MultiModalConversation

    system_text = context or "播客中文口语转录，保留口语化表达。"
    messages = [
        {"role": "system", "content": [{"text": system_text}]},
        {"role": "user", "content": [{"audio": str(audio_path.resolve())}]},
    ]
    asr_options = {"enable_itn": False}
    if language:
        asr_options["language"] = language

    model = os.getenv("QWEN_ASR_MODEL", "qwen3-asr-flash")
    response = MultiModalConversation.call(
        model=model,
        messages=messages,
        result_format="message",
        asr_options=asr_options,
    )
    return extract_text_from_response(response)


def transcribe_async_url(audio_url: str, language: str) -> str:
    dashscope = configure_dashscope()
    from dashscope.audio.asr import Transcription

    model = os.getenv("QWEN_ASR_FILE_MODEL", "qwen3-asr-flash-filetrans")
    params = {"channel_id": [0], "enable_itn": False}
    if language:
        params["language"] = language

    task = Transcription.async_call(model=model, file_urls=[audio_url], **params)
    if task.status_code != 200:
        raise RuntimeError(f"提交异步 ASR 失败: {task.code} {task.message}")

    task_id = task.output.task_id
    deadline = time.time() + int(os.getenv("ASR_ASYNC_TIMEOUT_SEC", "3600"))
    while time.time() < deadline:
        result = Transcription.wait(task=task_id)
        status = getattr(result.output, "task_status", None) or result.output.get(
            "task_status"
        )
        if status == "SUCCEEDED":
            return _parse_async_result(result)
        if status == "FAILED":
            raise RuntimeError(f"异步 ASR 失败: {result}")
        time.sleep(5)
    raise RuntimeError("异步 ASR 超时")


def _parse_async_result(result) -> str:
    output = result.output
    results = getattr(output, "results", None) or output.get("results", [])
    if not results:
        transcription_url = getattr(output, "transcription_url", None) or output.get(
            "transcription_url"
        )
        if transcription_url:
            import urllib.request

            raw = urllib.request.urlopen(transcription_url).read().decode("utf-8")
            return _text_from_transcription_json(json.loads(raw))
        raise RuntimeError(f"异步结果无文本: {output}")

    item = results[0]
    transcription_url = getattr(item, "transcription_url", None) or item.get(
        "transcription_url"
    )
    if transcription_url:
        import urllib.request

        raw = urllib.request.urlopen(transcription_url).read().decode("utf-8")
        return _text_from_transcription_json(json.loads(raw))

    text = getattr(item, "text", None) or item.get("text", "")
    if text:
        return text.strip()
    raise RuntimeError(f"无法从异步结果提取文本: {output}")


def _text_from_transcription_json(data: dict) -> str:
    transcripts = data.get("transcripts") or data.get("sentences") or []
    if isinstance(transcripts, list):
        parts = []
        for seg in transcripts:
            if isinstance(seg, dict):
                parts.append(seg.get("text") or seg.get("sentence", ""))
            elif isinstance(seg, str):
                parts.append(seg)
        text = "".join(parts).strip()
        if text:
            return text
    if "text" in data:
        return str(data["text"]).strip()
    raise RuntimeError(f"无法解析 transcription JSON: {list(data.keys())}")


def sanitize_filename(name: str, max_len: int = 80) -> str:
    illegal = '<>:"/\\|?*'
    cleaned = "".join(c for c in name if c not in illegal).strip()
    return (cleaned or "未命名")[:max_len]


def save_archive(text: str, show: str, title: str) -> Path:
    if show not in VALID_SHOWS:
        raise ValueError(f"节目名必须是: {', '.join(VALID_SHOWS)}")
    show_dir = ARCHIVE_DIR / show
    show_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{sanitize_filename(title)}_{date.today().strftime('%Y%m%d')}.txt"
    out_path = show_dir / filename
    out_path.write_text(f"# 转录稿\n\n{text.strip()}\n", encoding="utf-8")
    return out_path
