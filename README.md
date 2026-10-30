# MidBot

MidVC 的聊天机器人。这里是一个 monorepo，装着两代实现：

| 目录 | 是什么 | 状态 |
|---|---|---|
| `v1/` | 最早的 discord.py 版 MidBot（osu! 相关指令） | 已归档，不再运行 |
| `v2-early/` | 自写的 OneBot 11 适配器（接 NapCat，给微信/QQ 用） | 已被 AstrBot 取代 |
| `astrbot/plugins/` | 现在跑在 AstrBot 上的插件 | **在用** |
| `deploy/` | NapCat / AstrBot 的部署脚本 | 在用 |
| `docs/` | 架构、配置示例、踩坑记录 | — |

## 现在这套是怎么跑的

```
手机 QQ ── LinuxQQ(无头, Xvfb) ── NapCat ──OneBot11(反向WS)──> AstrBot ──> DeepSeek
                                                              Discord ──┘
```

- **AstrBot** 负责对话、人格、指令、平台适配。
- **NapCat** 只是 QQ 客户端的外挂，把 QQ 消息翻译成 OneBot 11。
- 三个插件补 AstrBot 没有的能力：
  - `group_whitelist`：群聊白名单，空的 = 哪个群都不说话。
  - `memlib_bridge`：把 `~/shared-memory/memory.json` 的长期记忆注入系统提示词，并在回复后抽取新事实，多平台共用一份记忆。
  - `midbot_legacy`：把 v1 的指令搬过来（ping / roll / mirror / ciallo / `>rs`）。

## 快速开始

1. 部署 AstrBot（见 `deploy/astrbot/`）。
2. 部署 NapCat（见 `deploy/napcat/`），让它反向 WS 连到 AstrBot 的 `ws://127.0.0.1:6199/ws`。
3. 把 `astrbot/plugins/` 里的三个目录复制到 AstrBot 的 `data/plugins/`。
4. 在 AstrBot 的 `data/cmd_config.json` 里填 provider、平台和 token（参考 `docs/cmd_config.example.json`）。

## 安全

仓库里**不放**任何 token / key / QQ 号 / 频道 ID。
真实配置在部署机的 `data/cmd_config.json`、`.env` 里，已被 `.gitignore` 排除。
