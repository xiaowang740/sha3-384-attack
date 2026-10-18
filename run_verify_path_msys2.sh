#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="${PYTHON_BIN:-}"
SOLVER="${SOLVER:-/d/cryptominisat5.exe}"
PATH_FILE="${PATH_FILE:-path_figure_raw.json}"
CNF_OUT="${CNF_OUT:-path_figure_raw_fixed_mod32.cnf}"
EXPECTED_WEIGHTS="${EXPECTED_WEIGHTS:-25,18,5}"

if [[ -z "$PYTHON_BIN" ]]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python3)"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python)"
    elif [[ -x "/c/Users/Lenovo/.conda/envs/dpa37/python.exe" ]]; then
        PYTHON_BIN="/c/Users/Lenovo/.conda/envs/dpa37/python.exe"
    else
        echo "错误：找不到 Python。请设置 PYTHON_BIN。" >&2
        exit 1
    fi
fi

if [[ ! -f "$PATH_FILE" ]]; then
    echo "错误：路径文件不存在：$PATH_FILE" >&2
    exit 1
fi

if [[ ! -f "verify_keccak_path.py" ]]; then
    echo "错误：找不到 verify_keccak_path.py" >&2
    exit 1
fi

echo "Python: $PYTHON_BIN"
echo "Solver: $SOLVER"
echo "Path: $PATH_FILE"
echo "CNF: $CNF_OUT"

"$PYTHON_BIN" verify_keccak_path.py \
    "$PATH_FILE" \
    --solver "$SOLVER" \
    --partial-b3 \
    --expected-weights "$EXPECTED_WEIGHTS" \
    --cnf-out "$CNF_OUT"

echo "验证完成。"
echo "查看 lane：${CNF_OUT%.cnf}.lanes.txt"
echo "查看全部变量：${CNF_OUT%.cnf}.variables.txt"
