#!/bin/zsh
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT"
PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  for candidate in python3.12 python3.13 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
      PYTHON_BIN="$candidate"
      break
    fi
  done
fi
if [[ -z "$PYTHON_BIN" ]] || ! command -v "$PYTHON_BIN" >/dev/null 2>&1 || ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
  echo "需要 Python 3.11 以上。推荐先执行：brew install python@3.12"
  read -r
  exit 1
fi
if [[ ! -x ".venv/bin/python" ]]; then
  "$PYTHON_BIN" -m venv .venv
fi
if ! .venv/bin/python -c "import PyQt6, cv2" >/dev/null 2>&1; then
  echo "首次安装 PyQt6 和 OpenCV 预编译依赖，请保持联网。"
  if ! .venv/bin/python -m pip install --only-binary=:all: -r requirements.txt; then
    echo "依赖安装失败。请核对 macOS 版本、网络和 Python 版本后重试。"
    read -r
    exit 1
  fi
fi
exec .venv/bin/python main.py
