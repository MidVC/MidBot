#!/bin/bash
# AstrBot 启动（tmux 常驻）
set -u
ASTRBOT_DIR="${ASTRBOT_DIR:-$HOME/astrbot}"
export PATH="$HOME/.local/bin:$PATH"

tmux kill-session -t astrbot 2>/dev/null
tmux new-session -d -s astrbot \
  "cd $ASTRBOT_DIR && uv run --no-sync main.py > $ASTRBOT_DIR/run.log 2>&1"
echo "AstrBot 启动中，日志：$ASTRBOT_DIR/run.log"
echo "WebUI：http://127.0.0.1:6185（建议 ssh -L 6185:127.0.0.1:6185 转发后访问）"
