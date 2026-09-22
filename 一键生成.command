#!/bin/zsh
set -e
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT"
PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "请先安装Python 3.11以上。建议：brew install python"
  read
  exit 1
fi
if [[ ! -x ".generator_venv/bin/python" ]]; then
  "$PYTHON_BIN" -m venv .generator_venv
fi
.generator_venv/bin/python -m pip install --disable-pip-version-check -q -r 工具/requirements-generator.txt
export PYTHONPATH="$ROOT/工具/.packages"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
exec .generator_venv/bin/python 工具/studio.py "$@"
