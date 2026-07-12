# podcast_deliver_assistant

播客交付助手 FastMCP 服务：音频转录 → 标题建议 → Shownotes 生成 → 发布稿存档。

演示节目：**二十而已**（可在 `config.yaml` / `host.md` 中自定义定位）。

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

- **LLM 模型**：编辑 `config.yaml` 的 `llm.model`，或设置环境变量 `PODCAST_LLM_MODEL`
- **节目定位**：编辑 `config.yaml` 的 `shows` 或 `host.md`
- **API Key**：通过 `.env` 设置 `DASHSCOPE_API_KEY`（不要提交到 Git）

## 目录结构

```
podcast_deliver_assistant/
├── podcast_deliver_mcp.py   # FastMCP 主服务
├── assistant_bot.py         # Qwen Agent 示例
├── transcribe.py            # Qwen3-ASR 转录
├── config.yaml              # LLM + 节目配置
├── host.md                  # 演示节目定位
├── archive/二十而已/        # 转录稿与发布稿存档
├── .env.example
└── requirements.txt
```

## License

MIT
