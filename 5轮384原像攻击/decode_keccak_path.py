#!/usr/bin/env python3
"""Decode one SAT model produced for the Keccak internal-difference CNF."""

import argparse
import json
import sys
from pathlib import Path


def read_model(path):
    values = {}
    # CryptoMiniSat writes many numeric values in comment/statistics lines.
    # Only parse literals from the actual model lines ("v ...").
    raw = Path(path).read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8"
    for line in raw.decode(encoding, errors="ignore").splitlines():
        line = line.strip()
        if not line.startswith("v "):
            continue
        for token in line[2:].split():
            try:
                literal = int(token)
            except ValueError:
                continue
            if literal:
                values[abs(literal)] = literal > 0
    if not values:
        raise ValueError("未找到 SAT 模型行（v ...）；请确认求解器输出为 SAT 模型")
    return values


def bits_to_int(bits, model):
    return sum((1 << i) for i, var in enumerate(bits) if model.get(var, False))


def decode_weights(data, model):
    result = []
    total = 0
    for item in data["round_transition_weights"]:
        boxes = []
        for box in item["boxes"]:
            if box.get("weight_encoding") == "unary_threshold":
                value = sum(
                    model.get(variable, False)
                    for variable in box["weight_bits"]
                )
            else:
                value = bits_to_int(box["weight_bits"], model)
            boxes.append({"y": box["y"], "z": box["z"], "weight": value})
            total += value
        result.append({"transition": item["transition"],
                       "weight": sum(box["weight"] for box in boxes), "boxes": boxes})
    return result, total


def format_lane_report(path):
    lines = ["32-bit lanes (8 hex digits); lane index = x + 5*y; rows y=0..4, columns x=0..4",
             "Bit z is bit (1 << z) of each lane.", ""]
    names = [name for name, values in path.items()
             if name[:1] in ("a", "b", "c") and name[1:].isdigit()
             and isinstance(values, list)]
    for name in sorted(names, key=lambda name: (int(name[1:]), {"b": 0, "c": 1, "a": 2}[name[0]])):
        lines.append(f"{name}:")
        for y in range(5):
            lines.append("|" + "|".join(path[name][y * 5:(y + 1) * 5]) + "|")
        lines.append("")
    for transition in path["transitions"]:
        r = transition["transition"]
        active = sum(bool(box["weight"]) for box in transition["boxes"])
        lines.append(f"transition {r} (b{r} -> c{r} -> a{r} -> b{r + 1}): "
                     f"weight={transition['weight']}, active_boxes={active}")
    lines.append(f"total_weight: {path['total_weight']}")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("--weights", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-transition-weight", type=int, default=None)
    parser.add_argument("--max-total-weight", type=int, default=None)
    parser.add_argument("--no-extend", action="store_true",
                        help="do not automatically extend b3 through c3 and a3")
    args = parser.parse_args()

    model = read_model(args.model)
    data = json.loads(Path(args.weights).read_text(encoding="ascii"))
    path = {"iota_start_round": data["iota_start_round"], "transitions": []}

    state_bits = {**data.get("path_a_bits", {}), **data.get("path_c_bits", {}),
                  **data["path_state_bits"]}
    for name in sorted(state_bits):
        if len(state_bits[name]) != 800:
            raise ValueError(f"{name}: expected 25 lanes of 32 bits")
        values = [
            bits_to_int(state_bits[name][lane * 32 : (lane + 1) * 32], model)
            for lane in range(25)
        ]
        path[name] = [f"{value:08x}" for value in values]

    transitions, total = decode_weights(data, model)
    if args.max_transition_weight is not None:
        overweight = [
            t for t in transitions
            if sum(box["weight"] for box in t["boxes"]) > args.max_transition_weight
        ]
        if overweight:
            details = ", ".join(
                f"transition {t['transition']}={sum(b['weight'] for b in t['boxes'])}"
                for t in overweight
            )
            raise SystemExit(
                f"路径不满足重量限制（上限 {args.max_transition_weight}）：{details}"
            )
    path["transitions"] = transitions
    path["total_weight"] = total
    if args.max_total_weight is not None and total > args.max_total_weight:
        raise SystemExit(
            f"路径不满足总重量限制（上限 {args.max_total_weight}）：total={total}"
        )
    if "total_weight_bits" in data:
        path["total_weight_bits_lsb_first"] = [
            int(model.get(var, False)) for var in data["total_weight_bits"]
        ]
    Path(args.out).write_text(
        json.dumps(path, indent=2, ensure_ascii=True) + "\n",
        encoding="ascii",
    )
    print(f"decoded path: {args.out}")
    report = format_lane_report(path)
    lanes_out = Path(args.out).with_suffix(".lanes.txt")
    lanes_out.write_text(report, encoding="ascii")
    if not args.no_extend and "b3" in path:
        from extend_keccak_path import process

        try:
            process(lanes_out, Path(args.out))
        except ValueError as error:
            print(f"automatic extension skipped: {error}", file=sys.stderr)
        else:
            report = lanes_out.read_text(encoding="ascii")
    print(f"lane view: {lanes_out}")
    print(report, end="", flush=True)


if __name__ == "__main__":
    main()
