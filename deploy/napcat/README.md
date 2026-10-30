# NapCat 无头部署（无 root）

目标：在一台没有 root、没有 Docker 的 Linux 上跑 LinuxQQ + NapCat，并把消息交给 AstrBot。

## 步骤

1. 用官方脚本 rootless 安装（装到 `~/Napcat`）：
   ```bash
   bash napcat.sh --docker n --cli n --proxy 0 --skip-deps
   ```
   依赖（xvfb、gtk3 等）在宿主机上通常已经齐了；缺 xkbcomp 不影响，下面用 chroot 绕过。

2. 准备一个 Debian rootfs（只为拿 `Xvfb` + `xkbcomp`），放在 `~/napcat-qq/rootfs`。

3. 配置 NapCat 反向 WS，指向 AstrBot：
   `~/Napcat/opt/QQ/resources/app/app_launcher/napcat/config/onebot11_<QQ号>.json`
   ```json
   {
     "network": {
       "httpServers": [],
       "websocketServers": [],
       "websocketClients": [{
         "name": "astrbot",
         "enable": true,
         "url": "ws://127.0.0.1:6199/ws",
         "messagePostFormat": "array",
         "reportSelfMessage": false,
         "reconnectInterval": 5000,
         "token": "<与 AstrBot 的 ws_reverse_token 一致>",
         "debug": false,
         "heartInterval": 30000
       }]
     },
     "musicSignUrl": "",
     "enableLocalFile2Url": true,
     "parseMultMsg": false
   }
   ```

4. 启动：
   ```bash
   QQ_NUMBER=123456789 ./start.sh
   ```
   第一次要扫二维码：`~/Napcat/opt/QQ/resources/app/app_launcher/napcat/cache/qrcode.png`。

## 说明

- QQ 登录成功后，重启 QQ 进程会走“快速登录”，不用反复扫码。
- 掉登录态多半是 QQ 风控；用手机 QQ 按提示验证后重新扫码。
- 端口：Xvfb `:20` → TCP 6020；NapCat WebUI 6099；AstrBot 6185 / OneBot 6199。
