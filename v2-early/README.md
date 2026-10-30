# v2-early：自写的 OneBot 11 适配器

在换到 AstrBot 之前，我们自己写的一套 QQ 机器人：复用 `bot_api.py` 的对话逻辑
（人格、记忆、群聊节奏、主动消息），只把收发层换成 OneBot 11（NapCat）。

- `bot_api.py`：对话核心（原本是微信 WeChatPadPro 版）。
- `qq_adapter.py`：QQ 适配层，连 NapCat 的正向 WS，用 HTTP API 发消息。

已被 AstrBot 版取代，留在这里当历史。要跑的话：把 `bot_config.example.json`
补成 `bot_config.json`（填 key、OneBot token 和自己的 QQ 号），装 `websockets`，然后
`python qq_adapter.py`。

注意：这套没有群白名单插件，群聊逻辑是内置的概率接话。
