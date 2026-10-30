# 架构与踩坑记录

## 组成

| 组件 | 位置（部署机） | 说明 |
|---|---|---|
| AstrBot | `~/astrbot` | 4.29.x，`uv` 管理依赖，WebUI 6185 |
| NapCat | `~/Napcat/opt/QQ/resources/app/app_launcher/napcat` | 4.18.x，rootless 装进 LinuxQQ |
| LinuxQQ | `~/Napcat/opt/QQ` | 3.2.34 |
| Xvfb | chroot `~/napcat-qq/rootfs` 内 | 显示 `:20`，只监听 TCP |
| 共享记忆 | `~/shared-memory/memory.json` | AstrBot 插件 + 微信 bot 共用 |

## 数据流

```
QQ 手机端
  ↕
LinuxQQ（无头，DISPLAY=127.0.0.1:20）
  ↕ NapCat 注入
NapCat ── 反向 WebSocket ──> AstrBot（aiocqhttp 适配器，127.0.0.1:6199/ws）
                                 ↕
                            DeepSeek API
Discord ── Gateway ────────────┘
```

## 踩过的坑

1. **无 root 环境**：用 `unshare -Ur` + chroot 跑 Debian 用户态。但 userns 只映射一个 uid/gid，
   `apt`/`dpkg` 里 chown 到 `_apt`/`adm` 会 EINVAL，所以 rootfs 不是 apt 装出来的。
2. **宿主机没有 xkbcomp**：Xvfb 直接跑会 `XKB: Failed to compile keymap`；
   把 Xvfb 放进 chroot（里面 `/usr/bin/xkbcomp` 在），QQ 用 `DISPLAY=127.0.0.1:20` 连 TCP 过去。
3. **端口冲突**：Xvfb 用 `:20`（6020），NapCat WebUI 默认 6099，别撞。
4. **PID namespace**：`unshare -p` 里 init 一退全死，所以 Xvfb 用 tmux 挂着。
5. **Discord 特权 intent**：AstrBot 同时要 Message Content 和 Server Members，
   没开的话登录静默失败（日志里看不出来）。
6. **AstrBot 的空白名单 ≠ 全禁**：它自带的 id_whitelist 为空表示“不检查”，
   所以群聊要不要说话得靠 `group_whitelist` 插件。
7. **QQ 风控**：新号容易触发“账号存在安全风险”，需要手机 QQ 验证；session 掉了要重新扫码。
