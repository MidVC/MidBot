#!/bin/bash
# NapCat 无头启动：Xvfb（chroot 内，自带 xkbcomp）+ LinuxQQ/NapCat
# 依赖：deploy/napcat/enter.sh、已安装的 ~/Napcat
# 可选环境变量：NAPCAT_DIR、XVFB_ROOTFS、DISPLAY_NUM、QQ_NUMBER
set -u

NAPCAT_DIR="${NAPCAT_DIR:-$HOME/Napcat}"
XVFB_ROOTFS="${XVFB_ROOTFS:-$HOME/napcat-qq}"
DISPLAY_NUM="${DISPLAY_NUM:-:20}"
BOT_DIR="$(cd "$(dirname "$0")" && pwd)"

if ! tmux has-session -t xvfb 2>/dev/null; then
  tmux new-session -d -s xvfb \
    "cd $XVFB_ROOTFS && $BOT_DIR/enter.sh \"exec /usr/bin/Xvfb $DISPLAY_NUM -screen 0 1280x800x24 -listen tcp -ac\""
  sleep 2
fi

if ! tmux has-session -t napcat 2>/dev/null; then
  tmux new-session -d -s napcat \
    "cd $NAPCAT_DIR && DISPLAY=127.0.0.1${DISPLAY_NUM#:} ./opt/QQ/qq --no-sandbox ${QQ_NUMBER:+-q $QQ_NUMBER} > $XVFB_ROOTFS/qq.log 2>&1"
  sleep 10
fi

echo "Xvfb:   $(tmux has-session -t xvfb 2>/dev/null && echo up || echo down)  (display 127.0.0.1${DISPLAY_NUM#:})"
echo "NapCat: $(tmux has-session -t napcat 2>/dev/null && echo up || echo down)"
