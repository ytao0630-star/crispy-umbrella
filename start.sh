#!/bin/bash
# 工业园区资管系统 · 一键启动后端
# 用法: bash start.sh   (在项目目录或任意位置均可)
set -e
cd "$(dirname "$0")"

PORT=8000
LOG=/tmp/park_backend.log

is_running() {
  python3 - <<'PY'
import socket
s = socket.socket()
try:
    s.connect(("127.0.0.1", 8000))
    s.close()
    print("RUNNING")
except Exception:
    print("FREE")
PY
}

if [ "$(is_running)" = "RUNNING" ]; then
  echo "[园区资管] 8000 已在运行 -> http://localhost:8000"
  exit 0
fi

echo "[园区资管] 正在启动后端 ..."
nohup python3 backend.py > "$LOG" 2>&1 &
disown
sleep 2.5

if curl -s -m 5 -o /dev/null "http://localhost:$PORT/"; then
  echo "[园区资管] 启动成功 -> http://localhost:$PORT  (日志: $LOG)"
else
  echo "[园区资管] 启动失败，请查看日志:"
  tail -20 "$LOG"
  exit 1
fi
