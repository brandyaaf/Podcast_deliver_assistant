"""从 host.md 读取节目名称与定位（单一配置源）。

修改 host.md 即可一键切换节目，无需改代码。
支持格式：
  单节目（推荐）—— 第一行 # 节目名，其余为定位正文
  多节目 —— 多个 # 节目名 分段，或 1. 节目名 编号分段
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
HOST_MD = REPO_ROOT / "host.md"

_cache = None


def _parse_host_md(content: str) -> dict:
    shows = {}
    content = content.strip()
    if not content:
        return shows

    # 格式1：# 节目名
    if "#" in content:
        sections = re.split(r"\n(?=#\s+)", content)
        for section in sections:
            section = section.strip()
            if not section.startswith("#"):
                continue
            lines = section.split("\n", 1)
            name = lines[0].lstrip("#").strip()
            body = lines[1].strip() if len(lines) > 1 else ""
            if name:
                shows[name] = body
        if shows:
            return shows

    # 格式2：1. 节目名（兼容多节目列表）
    pattern = r"(?:^|\n)\d+\.\s*(.+?)\s*\n([\s\S]*?)(?=\n\d+\.\s|\Z)"
    for match in re.finditer(pattern, content):
        name = match.group(1).strip()
        body = match.group(2).strip()
        if name:
            shows[name] = body

    return shows


def load_shows(force_reload: bool = False) -> dict:
    global _cache
    if _cache is not None and not force_reload:
        return _cache

    if not HOST_MD.is_file():
        _cache = {"我的播客": "节目定位：请在 host.md 中填写节目名称与定位。"}
        return _cache

    shows = _parse_host_md(HOST_MD.read_text(encoding="utf-8"))
    if not shows:
        raw = HOST_MD.read_text(encoding="utf-8").strip()
        _cache = {"我的播客": raw or "请在 host.md 填写节目定位。"}
    else:
        _cache = shows
    return _cache


def get_default_show() -> str:
    return next(iter(load_shows()))


def get_valid_shows() -> tuple:
    return tuple(load_shows().keys())


def get_show_positioning(show_name: str = "", override: str = "") -> str:
    if override.strip():
        return override.strip()

    shows = load_shows()
    name = (show_name or get_default_show()).strip()

    if name in shows and shows[name].strip():
        return shows[name].strip()

    if len(shows) == 1:
        return next(iter(shows.values())).strip()

    return f"节目：{name}"
