#!/usr/bin/env python3
"""Decode total weight bits from a DIMACS SAT solver model."""

import argparse
import json
from pathlib import Path


def read_model(path):
    model = {}
    text = Path(path).read_text(encoding="ascii", errors="ignore")
    for token in text.replace("\n", " ").split():
        try:
            value = int(token)
        except ValueError:
            continue
        if value:
            model[abs(value)] = value > 0
    return model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="DIMACS solver output, e.g. solver.out")
    parser.add_argument(
        "--weights",
        default="keccak_internal_diff_sat.weights.json",
        help="weight-variable mapping JSON",
    )
    args = parser.parse_args()

    model = read_model(args.model)
    data = json.loads(Path(args.weights).read_text(encoding="utf-8"))
    bits = data["total_weight_bits"]

    missing = [var for var in bits if var not in model]
    if missing:
        raise SystemExit(
            "模型中缺少 total_weight_bits 变量: "
            + ", ".join(map(str, missing))
        )

    total = sum((1 << i) for i, var in enumerate(bits) if model[var])
    bit_string = "".join("1" if model[var] else "0" for var in reversed(bits))
    print(f"total_weight_bits (MSB..LSB): {bit_string}")
    print(f"total_weight: {total}")


if __name__ == "__main__":
    main()
