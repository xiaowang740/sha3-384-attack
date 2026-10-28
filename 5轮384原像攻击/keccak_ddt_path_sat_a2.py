#!/usr/bin/env python3
"""Build a period-32 Keccak path CNF whose last explicit state is a2."""

import argparse
import json
from pathlib import Path

from keccak_ddt_path_sat import (
    Cnf,
    IOTA_RC_START,
    ROT,
    RC32,
    add_at_most,
    add_cp_kernel,
    add_ddt_chi_transition,
    add_iota,
    chi5,
    exactly_one,
    fi,
    linear_rows,
    ri,
)


TRANSITION_WEIGHT_LIMITS = (25, 20, 20)
TOTAL_WEIGHT_LIMIT = 65


def ddt_table():
    ddt = [[0] * 32 for _ in range(32)]
    for alpha in range(32):
        for value in range(32):
            ddt[alpha][chi5(value) ^ chi5(value ^ alpha)] += 1
    return ddt


def add_input_weight_lookup(c, a_bits, ddt, transition, meta):
    """Encode DDT weight thresholds from alpha; do not create Chi outputs."""
    row_weights = {}
    for alpha, row in enumerate(ddt):
        weights = {6 - count.bit_length() for count in row if count}
        if not weights:
            raise ValueError(f"DDT input {alpha} has no valid output")
        if len(weights) != 1:
            raise ValueError(
                f"DDT input {alpha} has non-unique output weights: {sorted(weights)}"
            )
        row_weights[alpha] = weights.pop()

    for y in range(5):
        for z in range(32):
            inputs = [a_bits[ri(x + 5 * y, z)] for x in range(5)]
            thresholds = [c.var() for _ in range(4)]
            meta["round_transition_weights"][transition]["boxes"].append(
                {
                    "y": y,
                    "z": z,
                    "weight_bits": thresholds,
                    "weight_encoding": "unary_threshold",
                }
            )
            for alpha, weight in row_weights.items():
                condition = [
                    -variable if (alpha >> bit) & 1 else variable
                    for bit, variable in enumerate(inputs)
                ]
                for threshold, variable in enumerate(thresholds, 1):
                    c.clause(
                        *condition,
                        variable if weight >= threshold else -variable,
                    )
            for index in range(1, 4):
                c.clause(-thresholds[index], thresholds[index - 1])


def build(start_round, limit, transition_limits=None, total_weight_limit=TOTAL_WEIGHT_LIMIT):
    if limit < 0:
        raise ValueError("limit must be non-negative")
    if transition_limits is None:
        transition_limits = list(TRANSITION_WEIGHT_LIMITS)
    if len(transition_limits) != 3 or any(value < 0 for value in transition_limits):
        raise ValueError("transition_limits must contain three non-negative values")
    if total_weight_limit < 0:
        raise ValueError("total_weight_limit must be non-negative")

    c = Cnf()
    rows = linear_rows()
    ddt = ddt_table()
    q = [c.var() for _ in range(21)]
    exactly_one(c, q)
    if start_round is not None:
        c.clause(q[start_round])

    b = [[c.var() for _ in range(800)] for _ in range(3)]
    c.clause(*b[0])
    meta = {
        "model": "period-32 Keccak differential path ending at a2",
        "lane_indexing": "x+5*y",
        "period_bits": 32,
        "linear_z_modulus": 32,
        "iota_encoding": "rc_low32_xor_high32",
        "cp_kernel_states": ["c1", "c2"],
        "weight_limit_scope": "per_transition_and_total",
        "transition_weight_limits": list(transition_limits),
        "total_weight_limit": total_weight_limit,
        "iota_rc_start": IOTA_RC_START,
        "iota_start_round": start_round,
        "transition_count": 3,
        "explicit_final_state": "a2",
        "omitted_states": ["b3", "c3", "a3"],
        "transition_2_weight_source": "a2_input_ddt_row",
        "transition_2_weight_encoding": "unary_threshold",
        "weight_definition": "-log2(DDT/32); DDT 32,16,8,4,2 => weight 0,1,2,3,4",
        "weight_encoding": {
            "bits_lsb_first": ["w0", "w1", "w2"],
            "0": "000",
            "1": "001",
            "2": "010",
            "3": "011",
            "4": "100",
        },
        "chi_ddt_nonzero_counts": sorted({v for row in ddt for v in row if v}),
        "round_transition_weights": [
            {"transition": r, "boxes": []} for r in range(3)
        ],
        "path_a_bits": {},
        "path_c_bits": {},
        "path_state_bits": {
            "b0": b[0],
            "b1": b[1],
            "b2": b[2],
        },
    }

    total_terms = []
    for r in range(3):
        a = [c.var() for _ in range(800)]
        meta["path_a_bits"][f"a{r}"] = a
        c_bits = [c.var() for _ in range(800)]
        meta["path_c_bits"][f"c{r}"] = c_bits
        add_iota(c, b[r], c_bits, q, r)
        if r in (1, 2):
            add_cp_kernel(c, c_bits)
        for out_bit, source_bits in enumerate(rows):
            c.xor_eq(a[out_bit], (c_bits[src] for src in source_bits))

        if r < 2:
            add_ddt_chi_transition(c, a, b[r + 1], ddt, r, meta)
        else:
            meta["path_state_bits"]["a2"] = a
            add_input_weight_lookup(c, a, ddt, r, meta)

        terms = []
        for box in meta["round_transition_weights"][r]["boxes"]:
            weight_bits = box["weight_bits"]
            if box.get("weight_encoding") == "unary_threshold":
                terms.extend(weight_bits)
            else:
                w0, w1, w2 = weight_bits
                terms += [w2] * 4 + [w1] * 2 + [w0]
        total_terms.extend(terms)
        add_at_most(c, terms, transition_limits[r])

    add_at_most(c, total_terms, total_weight_limit)
    meta["max_transition_weight"] = max(transition_limits)
    return c, meta


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--weights", required=True)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--transition-limits", default="25,20,20")
    parser.add_argument("--total-weight-limit", type=int, default=TOTAL_WEIGHT_LIMIT)
    parser.add_argument("--start-round", type=int, choices=range(21), default=None)
    args = parser.parse_args()

    limits = [int(value) for value in args.transition_limits.split(",")]
    cnf, metadata = build(
        args.start_round,
        args.limit,
        limits,
        args.total_weight_limit,
    )
    cnf.write(args.out)
    Path(args.weights).write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.out}: {cnf.nvars} variables, {len(cnf.clauses)} clauses")
    print(
        f"Wrote {args.weights}; transition limits = {limits}; "
        f"total weight <= {args.total_weight_limit}; explicit final state = a2"
    )


if __name__ == "__main__":
    main()
