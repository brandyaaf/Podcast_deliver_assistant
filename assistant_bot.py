"""Qwen Agent 接入 podcast_deliver_assistant MCP 的示例助手。"""

import os
from pathlib import Path
from typing import Optional

import dashscope
import yaml
from qwen_agent.agents import Assistant
from qwen_agent.gui import WebUI

from host_config import get_default_show, get_valid_shows

REPO_ROOT = Path(__file__).resolve().parent
MCP_SCRIPT = REPO_ROOT / "podcast_deliver_mcp.py"
MCP_PORT = 6278

dashscope.api_key = os.getenv("DASHSCOPE_API_KEY", "")
dashscope.timeout = 60


def init_agent_service():
    config_path = REPO_ROOT / "config.yaml"
    llm_cfg = {"model": "qwen-max", "timeout": 60, "retry_count": 3}
    if config_path.is_file():
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        llm_cfg.update(cfg.get("llm") or {})

    env_model = os.getenv("PODCAST_LLM_MODEL", "").strip()
    if env_model:
        llm_cfg["model"] = env_model

    default_show = get_default_show()
    valid_shows = " / ".join(get_valid_shows())

    system = (
        "你是播客交付助手，帮助创作者根据音频或转录稿生成标题与 Shownotes。"
        "当用户提供 MP3/WAV 时，调用 podcast_deliver_assistant 或 transcribe_podcast_audio 做真实 ASR，"
        "不要手写模拟转录稿。节目名称与定位统一从 host.md 读取，"
        f"当前默认节目为「{default_show}」（可选：{valid_shows}）。"
        "缺音频和转录文本时，提示「请先上传音频文件或粘贴转录文本」。"
    )

    tools = [{
        "mcpServers": {
            "podcast-deliver": {
                "command": "python",
                "args": [str(MCP_SCRIPT)],
                "port": MCP_PORT,
            }
        }
    }]

    bot = Assistant(
        llm=llm_cfg,
        name="podcast_deliver_assistant",
        description="播客标题与 Shownotes 生成",
        system_message=system,
        function_list=tools,
    )
    print("podcast_deliver_assistant 初始化成功！")
    return bot


def test(
    query: str = "请为这期节目生成标题和 shownotes",
    file: Optional[str] = None,
    show: str = "",
):
    bot = init_agent_service()
    messages = []
    show = show.strip() or get_default_show()
    content = f"节目：{show}\n{query}"
    if not file:
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": [{"text": content}, {"file": file}]})

    print("正在处理您的请求...")
    for response in bot.run(messages):
        print("bot response:", response)


def app_tui():
    bot = init_agent_service()
    messages = []
    while True:
        try:
            query = input("user question: ")
            show = input(f"节目名（回车默认 {get_default_show()}）: ").strip() or get_default_show()
            file = input("file url (press enter if no file): ").strip()
            if not query:
                print("user question cannot be empty！")
                continue

            content = f"节目：{show}\n{query}"
            if not file:
                messages.append({"role": "user", "content": content})
            else:
                messages.append({"role": "user", "content": [{"text": content}, {"file": file}]})

            print("正在处理您的请求...")
            response = []
            for response in bot.run(messages):
                print("bot response:", response)
            messages.extend(response)
        except Exception as e:
            print(f"处理请求时出错: {str(e)}")


def app_gui():
    print("正在启动 Web 界面...")
    bot = init_agent_service()
    default_show = get_default_show()
    chatbot_config = {
        "prompt.suggestions": [
            f"请为这期「{default_show}」生成 5 个标题和 shownotes（我已粘贴转录稿）",
            "上传 MP3 后，为这期节目生成标题和 shownotes",
            "根据转录稿生成导语、时间戳、金句和互动问题",
            "分析转录稿并给出个人推荐 TOP 1 标题",
        ]
    }
    WebUI(bot, chatbot_config=chatbot_config).run()


if __name__ == "__main__":
    app_gui()
