#!/bin/bash
# 建筑能源智能管理系统 启动脚本
# Windows 用户请使用 Git Bash 运行: bash start.sh
# macOS/Linux 用户可直接运行: ./start.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
DATA_DIR="$SCRIPT_DIR/data"
VUE_DIR="$SCRIPT_DIR/frontend-vue"

PY_BACKEND_DIR="$BACKEND_DIR"
PY_DATA_DIR="$DATA_DIR"

echo "=============================================="
echo "  建筑能源智能管理系统 - 启动脚本"
echo "=============================================="

# 自动检测 Python 可执行文件（兼容 Windows/macOS/Linux）
PYTHON_BIN=""
PYTHON_ARGS=()
FALLBACK_BIN=""
FALLBACK_ARGS=()
FOUND_ANY_PYTHON=0

try_python_with_pip() {
  local bin="$1"
  shift

  if ! command -v "$bin" &>/dev/null; then
    return 1
  fi

  FOUND_ANY_PYTHON=1

  if [ -z "$FALLBACK_BIN" ]; then
    FALLBACK_BIN="$bin"
    FALLBACK_ARGS=("$@")
  fi

  if "$bin" "$@" -m pip --version &>/dev/null; then
    PYTHON_BIN="$bin"
    PYTHON_ARGS=("$@")
    return 0
  fi

  return 1
}

run_python() {
  "$PYTHON_BIN" "${PYTHON_ARGS[@]}" "$@"
}

to_windows_path() {
  local p="$1"

  if command -v wslpath &>/dev/null; then
    wslpath -m "$p" 2>/dev/null && return 0
  fi

  if command -v cygpath &>/dev/null; then
    cygpath -m "$p" 2>/dev/null && return 0
  fi

  if [[ "$p" =~ ^/mnt/([a-zA-Z])/(.*)$ ]]; then
    local drive="${BASH_REMATCH[1]}"
    local rest="${BASH_REMATCH[2]}"
    echo "${drive^^}:/$rest"
    return 0
  fi

  if [[ "$p" =~ ^/([a-zA-Z])/(.*)$ ]]; then
    local drive="${BASH_REMATCH[1]}"
    local rest="${BASH_REMATCH[2]}"
    echo "${drive^^}:/$rest"
    return 0
  fi

  echo "$p"
}

# Windows/Git Bash 下优先使用 py 启动器，避免误选 /usr/bin/python3
try_python_with_pip py -3 || \
try_python_with_pip py.exe -3 || \
try_python_with_pip /c/Windows/py.exe -3 || \
try_python_with_pip python || \
try_python_with_pip python.exe || \
try_python_with_pip python3 || \
try_python_with_pip python3.exe || \
try_python_with_pip py || \
try_python_with_pip py.exe || \
try_python_with_pip /c/Windows/py.exe

if [ -z "$PYTHON_BIN" ] && [ -n "$FALLBACK_BIN" ]; then
  echo "未检测到可用 pip，尝试通过 ensurepip 修复..."
  "$FALLBACK_BIN" "${FALLBACK_ARGS[@]}" -m ensurepip --upgrade &>/dev/null || true

  if "$FALLBACK_BIN" "${FALLBACK_ARGS[@]}" -m pip --version &>/dev/null; then
    PYTHON_BIN="$FALLBACK_BIN"
    PYTHON_ARGS=("${FALLBACK_ARGS[@]}")
  fi
fi

if [ -z "$PYTHON_BIN" ]; then
  if [ "$FOUND_ANY_PYTHON" -eq 1 ]; then
    echo "错误：已检测到 Python，但 pip 不可用。"
    echo "请先执行：py -3 -m ensurepip --upgrade"
    echo "然后执行：py -3 -m pip install -r backend/requirements.txt"
  else
    echo "错误：未找到 Python，请先安装 Python 3.8+。"
    echo "下载地址: https://www.python.org/downloads/"
  fi
  exit 1
fi

echo "使用 Python: $(run_python --version 2>&1)"

# WSL/Git Bash 下若使用 Windows Python，需将路径转换为 C:/... 形式
PY_OS_NAME="$(run_python -c 'import os; print(os.name)' 2>/dev/null | tr -d '\r\n')"
if [ "$PY_OS_NAME" = "nt" ]; then
  PY_BACKEND_DIR="$(to_windows_path "$BACKEND_DIR")"
  PY_DATA_DIR="$(to_windows_path "$DATA_DIR")"
fi

# 安装依赖
echo ""
echo "[1/3] 检查并安装 Python 依赖..."
if ! run_python -m pip install -r "$PY_BACKEND_DIR/requirements.txt" -q; then
  echo "错误：Python 依赖安装失败，请检查解释器与 requirements 路径。"
  exit 1
fi
echo "Python 依赖安装完成 ✓"

# （可选）构建 Vue 前端
echo ""
echo "[2/3] 检查前端（Vue）..."
if command -v npm &>/dev/null && [ -f "$VUE_DIR/package.json" ]; then
  if [ ! -d "$VUE_DIR/dist" ] || [ "$VUE_DIR/src" -nt "$VUE_DIR/dist" ]; then
    echo "检测到前端源码有更新，正在构建 Vue 前端..."
    (cd "$VUE_DIR" && npm install -q 2>/dev/null && npm run build)
    echo "Vue 前端构建完成 ✓"
  else
    echo "Vue 前端已是最新，跳过构建 ✓"
  fi
else
  echo "（未检测到 npm，使用预构建的 Vue dist）✓"
fi

# 启动后端服务（数据库表会在应用启动时自动初始化）
echo ""
echo "[3/3] 启动后端服务..."
echo ""
echo "系统访问地址："
echo "  Web界面: http://localhost:8000"
echo "  API文档: http://localhost:8000/docs"
echo "  健康检查: http://localhost:8000/health"
echo ""
echo "按 Ctrl+C 停止服务"
echo "=============================================="

USER_STOPPED=0
trap 'USER_STOPPED=1' INT TERM

START_TS=$(date +%s)
run_python -m uvicorn app:app --app-dir "$PY_BACKEND_DIR" --host 0.0.0.0 --port 8000
UVICORN_EXIT_CODE=$?
END_TS=$(date +%s)
RUNTIME_SECONDS=$((END_TS - START_TS))

# Ctrl+C/终止信号属于用户主动停止，不应显示启动失败
if [ "$USER_STOPPED" -eq 1 ] || [ "$UVICORN_EXIT_CODE" -eq 130 ] || [ "$UVICORN_EXIT_CODE" -eq 143 ]; then
  echo ""
  echo "服务已停止。"
  exit 0
fi

# 某些终端（如部分 Git Bash）在 Ctrl+C 后会返回退出码 1。
# 若服务已运行一段时间再退出，通常是用户主动停止而非启动失败。
if [ "$UVICORN_EXIT_CODE" -eq 1 ] && [ "$RUNTIME_SECONDS" -ge 2 ]; then
  echo ""
  echo "服务已停止。"
  exit 0
fi

if [ "$UVICORN_EXIT_CODE" -ne 0 ]; then
  echo "错误：后端服务启动失败（退出码: $UVICORN_EXIT_CODE）。"
  exit "$UVICORN_EXIT_CODE"
fi
