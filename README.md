# podcast_deliver_assistant

播客交付助手 FastMCP 服务：音频转录 → 标题建议 → Shownotes 生成 → 发布稿存档。

演示节目默认 **二十而已**，只需编辑 `host.md` 即可一键切换节目名称与定位。

## 功能

| Tool | 说明 |
|------|------|
| `podcast_deliver_assistant` | 一站式：转录 + 生成标题与 Shownotes |
| `transcribe_podcast_audio` | Qwen3-ASR 音频转文字 |
| `generate_titles_and_shownotes` | 根据转录稿生成文案 |
| `save_final_release` | 追加最终发布稿到 archive |

## 快速开始

```bash
git clone https://github.com/<your-username>/podcast_deliver_assistant.git
cd podcast_deliver_assistant
pip install -r requirements.txt
cp .env.example .env   # 填入 DASHSCOPE_API_KEY
```

### 单独运行 MCP Server

```bash
python podcast_deliver_mcp.py
```

### Qwen Agent 示例（GUI）

```bash
python assistant_bot.py
```

### 在 Cursor / Claude Desktop 中配置 MCP

```json
{
  "mcpServers": {
    "podcast-deliver": {
      "command": "python",
      "args": ["/path/to/podcast_deliver_mcp.py"]
    }
  }
}
```

## 配置

- **节目名称 + 定位（一键修改）**：只改 `host.md`
  ```markdown
  # 你的节目名

  节目定位：...
  风格要求：...
  ```
  第一行 `# 节目名` 决定节目名，其余正文为定位；存档目录自动变为 `archive/<节目名>/`。
- **LLM 模型**：编辑 `config.yaml` 的 `llm.model`，或设置环境变量 `PODCAST_LLM_MODEL`
- **API Key**：通过 `.env` 设置 `DASHSCOPE_API_KEY`（不要提交到 Git）

## 目录结构

```
podcast_deliver_assistant/
├── podcast_deliver_mcp.py   # FastMCP 主服务
├── assistant_bot.py         # Qwen Agent 示例
├── transcribe.py            # Qwen3-ASR 转录
├── host_config.py           # 解析 host.md
├── config.yaml              # 仅 LLM 配置
├── host.md                  # 节目名称与定位（单一配置源）
├── archive/<节目名>/        # 转录稿与发布稿存档（随 host.md 自动切换）
├── .env.example
└── requirements.txt
```

## License

MIT
