#!/bin/bash
# 工业园区资管系统 —— 常驻启动脚本（脱离 WorkBuddy 会话，避免被回收）
# 用法：
#   ./start-daemon.sh          启动（默认 8000 端口）
#   ./start-daemon.sh 9000     自定义端口
#   ./start-daemon.sh stop     停止已在运行的服务
set -e
cd "$(dirname "$0")"
PORT="${1:-8000}"

if [ "$1" = "stop" ]; then
  pkill -f "backend.py" && echo "已停止服务" || echo "没有运行中的服务"
  exit 0
fi

# 先停止旧进程，避免端口冲突
pkill -f "backend.py" 2>/dev/null || true
sleep 1

PORT="$PORT" /usr/bin/python3 - <<'PY'
import subprocess, os
log = open('/tmp/park_server.log', 'a')
subprocess.Popen(
    ['/usr/bin/python3', 'backend.py'],
    cwd=os.getcwd(),
    env={**os.environ, 'PORT': os.environ.get('PORT', '8000')},
    stdout=log,
    stderr=subprocess.STDOUT,
    start_new_session=True,
)
print('park asset manager started on http://127.0.0.1:' + os.environ.get('PORT', '8000'))
PY
