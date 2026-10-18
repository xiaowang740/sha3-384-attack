#!/usr/bin/env python3
"""Replay a decoded path by fixing every a/b state bit in the DDT CNF."""

import argparse
import json
import subprocess
from pathlib import Path

from keccak_ddt_path_sat import IOTA_RC_START, RC32, build


def lane_hex_to_bits(values):
    if len(values) != 25:
        raise ValueError(f"expected 25 lanes, got {len(values)}")
    bits = []
    for value in values:
        if value is None:
            bits.extend([None] * 32)
        else:
            bits.extend((int(value.replace("-", "0"), 16) >> z) & 1 for z in range(32))
    return bits


def iota_xor_values(values, round_index):
    result = []
    for lane, value in enumerate(values):
        if value is None:
            result.append(None)
            continue
        number = int(value.replace("-", "0"), 16)
        if lane == 0:
            number ^= RC32[IOTA_RC_START + round_index]
        result.append(f"{number:08x}")
    return result


def ddt_table():
    def chi5(value):
        return sum(
            (
                ((value >> x) & 1)
                ^ (((1 ^ ((value >> ((x + 1) % 5)) & 1))
                    & ((value >> ((x + 2) % 5)) & 1)))
            ) << x
            for x in range(5)
        )

    table = [[0] * 32 for _ in range(32)]
    for alpha in range(32):
        for value in range(32):
            table[alpha][chi5(value) ^ chi5(value ^ alpha)] += 1
    return table


def path_weights(path, ddt):
    expected = []
    for transition in range(3):
        a = lane_hex_to_bits(path[f"a{transition}"])
        b = lane_hex_to_bits(path[f"b{transition + 1}"])
        boxes = []
        for y in range(5):
            for z in range(32):
                alpha_bits = [a[(x + 5 * y) * 32 + z] for x in range(5)]
                beta_bits = [b[(x + 5 * y) * 32 + z] for x in range(5)]
                if None in alpha_bits or None in beta_bits:
                    boxes.append({"y": y, "z": z, "weight": None})
                    continue
                alpha = sum(alpha_bits[x] << x for x in range(5))
                beta = sum(beta_bits[x] << x for x in range(5))
                count = ddt[alpha][beta]
                weight = None if count == 0 else 6 - count.bit_length()
                boxes.append({"y": y, "z": z, "weight": weight})
        expected.append(boxes)
    return expected


def read_model(text):
    model = {}
    for line in text.splitlines():
        if not line.startswith("v "):
            continue
        for token in line[2:].split():
            literal = int(token)
            if literal:
                model[abs(literal)] = literal > 0
    return model


def lane_hex_values(variables, model):
    values = []
    for lane in range(25):
        value = sum(
            (1 << z) for z, variable in enumerate(variables[lane * 32:(lane + 1) * 32])
            if model.get(variable, False)
        )
        values.append(f"{value:08x}")
    return values


def write_lane_view(path, variables_by_name, model):
    with path.open("w", encoding="ascii", newline="\n") as output:
        for name in ("b0", "c0", "a0", "b1", "c1", "a1", "b2", "c2", "a2", "b3"):
            output.write(f"{name}:\n")
            values = lane_hex_values(variables_by_name[name], model)
            for y in range(5):
                row = values[y * 5:(y + 1) * 5]
                output.write("|" + "|".join(row) + "|\n")
            output.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--solver", required=True)
    parser.add_argument("--start-round", type=int, default=None)
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--cnf-out", type=Path, default=Path("fixed_path.cnf"))
    parser.add_argument(
        "--partial-b3",
        action="store_true",
        help="only fix b3 lanes 13..24; leave lanes 0..12 free",
    )
    parser.add_argument(
        "--expected-weights",
        default="25,18,5",
        help="expected transition weights, comma-separated",
    )
    parser.add_argument("--model-out", type=Path, default=None)
    parser.add_argument("--variables-out", type=Path, default=None)
    parser.add_argument("--lanes-out", type=Path, default=None)
    args = parser.parse_args()

    path = json.loads(args.path.read_text(encoding="utf-8"))
    start_round = path.get("iota_start_round") if args.start_round is None else args.start_round
    c, meta = build(start_round, args.limit)
    if (
        meta.get("lane_indexing") != "x+5*y"
        or meta.get("period_bits") != 32
        or meta.get("linear_z_modulus") != 32
        or meta.get("iota_encoding") != "rc_low32_xor_high32"
        or meta.get("cp_kernel_states") != ["c1", "c2"]
        or meta.get("weight_limit_scope") != "per_transition"
        or meta.get("transition_weight_limits") != [25, 20, 20]
        or meta.get("iota_rc_start") != 2
    ):
        raise RuntimeError("verification requires the 800-bit mod-32 encoding with CP(c1,c2), RC[1], and per-transition limits")
    expected = path_weights(path, ddt_table())

    declared = path.get("transitions")
    expected_weights = [int(value) for value in args.expected_weights.split(",")]
    mismatches = []
    invalid = []
    for transition, boxes in enumerate(expected):
        if args.partial_b3 and transition == 2:
            continue
        for box in boxes:
            if declared is None:
                continue
            declared_weight = declared[transition]["boxes"][box["y"] * 32 + box["z"]]["weight"]
            if box["weight"] is None:
                invalid.append((transition, box["y"], box["z"]))
            elif declared_weight != box["weight"]:
                mismatches.append((transition, box["y"], box["z"], declared_weight, box["weight"]))

    fixed_variables = {**meta["path_a_bits"], **meta["path_state_bits"]}
    for name, variables in fixed_variables.items():
        bits = lane_hex_to_bits(path[name])
        lanes = range(13, 25) if args.partial_b3 and name == "b3" else range(25)
        for lane in lanes:
            start = lane * 32
            for variable, bit in zip(variables[start:start + 32], bits[start:start + 32]):
                c.clause(variable if bit else -variable)

    fixed_c = {}
    for transition in range(3):
        values = iota_xor_values(path[f"b{transition}"], transition)
        fixed_c[f"c{transition}"] = values
        bits = lane_hex_to_bits(values)
        variables = meta["path_c_bits"][f"c{transition}"]
        for variable, bit in zip(variables, bits):
            if bit is not None:
                c.clause(variable if bit else -variable)

    path_variables = {**fixed_variables, **meta["path_c_bits"]}

    c.write(args.cnf_out)
    print(f"fixed CNF: {args.cnf_out}")
    c_values_out = args.cnf_out.with_suffix(".fixed-c.lanes.txt")
    with c_values_out.open("w", encoding="ascii", newline="\n") as output:
        for name in ("c0", "c1", "c2"):
            output.write(f"{name}:\n")
            for y in range(5):
                row = fixed_c[name][y * 5:(y + 1) * 5]
                output.write("|" + "|".join(row) + "|\n")
            output.write("\n")
    print(f"fixed c lane view: {c_values_out}")
    print(f"declared total weight: {path.get('total_weight', 'missing')}")
    known_weight = sum(
        box["weight"] or 0
        for boxes in expected
        for box in boxes
        if box["weight"] is not None
    )
    print(f"recomputed known DDT weight: {known_weight}")
    print(f"invalid DDT boxes: {len(invalid)}")
    print(f"weight mismatches: {len(mismatches)}")
    if invalid:
        print(f"first invalid box: transition={invalid[0][0]}, y={invalid[0][1]}, z={invalid[0][2]}")
    if mismatches:
        print(f"first weight mismatch: transition,y,z,declared,expected={mismatches[0]}")

    result = subprocess.run(
        [args.solver, str(args.cnf_out)],
        capture_output=True,
        text=True,
    )
    model_text = result.stdout + result.stderr
    if result.returncode == 10 or "s SATISFIABLE" in model_text:
        print("SAT: fixed a/b path is accepted by the CNF")
        model = read_model(model_text)
        model_out = args.model_out or args.cnf_out.with_suffix(".model.txt")
        variables_out = args.variables_out or args.cnf_out.with_suffix(".variables.txt")
        lanes_out = args.lanes_out or args.cnf_out.with_suffix(".lanes.txt")
        model_out.write_text(model_text, encoding="utf-8")
        with variables_out.open("w", encoding="ascii", newline="\n") as output:
            for variable in range(1, c.nvars + 1):
                output.write(f"{variable} {1 if model.get(variable, False) else 0}\n")
        all_path_variables = {
            **meta["path_state_bits"],
            **meta["path_c_bits"],
            **meta["path_a_bits"],
        }
        write_lane_view(lanes_out, all_path_variables, model)
        print(f"SAT model: {model_out}")
        print(f"all variable values: {variables_out}")
        print(f"lane view: {lanes_out}")
        solved_weights = []
        for transition in meta["round_transition_weights"]:
            total = 0
            for box in transition["boxes"]:
                bits = box["weight_bits"]
                total += sum((1 << i) for i, variable in enumerate(bits) if model.get(variable, False))
            solved_weights.append(total)
        print(f"SAT model transition weights: {solved_weights}")
        if solved_weights != expected_weights:
            print(f"WEIGHT MISMATCH: expected {expected_weights}")
        else:
            print("WEIGHT CHECK: PASS")
        if args.partial_b3:
            print("b3 fixed lanes: 13..24; b3 lanes 0..12 were selected by SAT")
    elif result.returncode == 20 or "s UNSATISFIABLE" in model_text:
        print("UNSAT: fixed a/b path is rejected by the CNF")
    else:
        print(model_text, end="")
        raise SystemExit(f"solver failed with exit code {result.returncode}")


if __name__ == "__main__":
    main()
