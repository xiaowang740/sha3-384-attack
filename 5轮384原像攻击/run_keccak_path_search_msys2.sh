#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Override these variables on the command line when needed.
MAX_WEIGHT="${MAX_WEIGHT:-30}"
TRANSITION_LIMITS="${TRANSITION_LIMITS:-25,20,20}"
TOTAL_WEIGHT_LIMIT="${TOTAL_WEIGHT_LIMIT:-65}"
COUNT="${COUNT:-10}"
START_ROUND="${START_ROUND:-0}"
OUTPUT_DIR="${OUTPUT_DIR:-keccak_path_results_msys2}"
SOLVER="${SOLVER:-}"
PYTHON_BIN="${PYTHON_BIN:-}"

if [[ -z "$PYTHON_BIN" ]]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python3)"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python)"
    elif [[ -x "/c/Users/Lenovo/.conda/envs/dpa37/python.exe" ]]; then
        PYTHON_BIN="/c/Users/Lenovo/.conda/envs/dpa37/python.exe"
    else
        echo "错误：找不到 Python。请设置 PYTHON_BIN，例如：" >&2
        echo '  PYTHON_BIN=/c/Users/Lenovo/.conda/envs/dpa37/python.exe ./run_keccak_path_search_msys2.sh' >&2
        exit 1
    fi
fi

if [[ -z "$SOLVER" ]]; then
    for candidate in cryptominisat5 kissat cadical minisat; do
        if command -v "$candidate" >/dev/null 2>&1; then
            SOLVER="$(command -v "$candidate")"
            break
        fi
    done
fi

if [[ -z "$SOLVER" ]]; then
    echo "错误：找不到 SAT 求解器。请设置，例如：" >&2
    echo '  SOLVER=/d/cryptominisat5.exe ./run_keccak_path_search_msys2.sh' >&2
    exit 1
fi

if (( START_ROUND >= 0 )); then
    ROUND_TAG="r${START_ROUND}"
else
    ROUND_TAG="anyround"
fi
LIMIT_TAG="${TRANSITION_LIMITS//,/_}"
CNF="keccak_internal_diff_sat_${ROUND_TAG}_ddt_w${LIMIT_TAG}.cnf"
WEIGHTS="keccak_internal_diff_sat_${ROUND_TAG}_ddt_w${LIMIT_TAG}.weights.json"

GENERATOR_ARGS=(
    keccak_ddt_path_sat.py
    --out "$CNF"
    --weights "$WEIGHTS"
    --limit "$MAX_WEIGHT"
    --transition-limits "$TRANSITION_LIMITS"
    --total-weight-limit "$TOTAL_WEIGHT_LIMIT"
)
if (( START_ROUND >= 0 )); then
    GENERATOR_ARGS+=(--start-round "$START_ROUND")
fi

echo "Python: $PYTHON_BIN"
echo "Solver: $SOLVER"
echo "Generating: $CNF"
"$PYTHON_BIN" "${GENERATOR_ARGS[@]}"

mkdir -p "$OUTPUT_DIR"
echo "Running SAT search..."
"$PYTHON_BIN" enumerate_keccak_paths.py \
    --solver "$SOLVER" \
    --cnf "$CNF" \
    --weights "$WEIGHTS" \
    --outdir "$OUTPUT_DIR" \
    --count "$COUNT" \
    --max-total-weight "$TOTAL_WEIGHT_LIMIT"

echo "Output: $OUTPUT_DIR"
