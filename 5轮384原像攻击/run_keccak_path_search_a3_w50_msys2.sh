#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export PATH="/mingw64/bin:/ucrt64/bin:$PATH"
export PYTHONPATH="$SCRIPT_DIR/.sat-deps${PYTHONPATH:+:$PYTHONPATH}"

PYTHON_BIN="${PYTHON_BIN:-/c/ProgramData/Anaconda3/python.exe}"
SOLVER="${SOLVER:-/d/cryptominisat5.exe}"
COUNT="${COUNT:-50}"
THREADS="${THREADS:-2}"
OUTPUT_DIR="${OUTPUT_DIR:-a3_w0_50_obj170_$(date +%Y%m%d_%H%M%S)}"

if [[ ! -x "$PYTHON_BIN" || ! -x "$SOLVER" ]]; then
    echo 'Python or solver executable not found; set PYTHON_BIN and SOLVER.' >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIR"
"$PYTHON_BIN" keccak_ddt_path_sat_a3_w50_weighted.py \
    --out "$OUTPUT_DIR/path.cnf" \
    --weights "$OUTPUT_DIR/path.weights.json" \
    --start-round 0 \
    --transition0-limit 50 \
    --objective-limit 170

"$PYTHON_BIN" -u enumerate_keccak_paths_a3_w50_weighted.py \
    --solver "$(cygpath -w "$SOLVER")" \
    --cnf "$OUTPUT_DIR/path.cnf" \
    --weights "$OUTPUT_DIR/path.weights.json" \
    --outdir "$OUTPUT_DIR" \
    --count "$COUNT" \
    --threads "$THREADS"

echo "Output: $OUTPUT_DIR"
