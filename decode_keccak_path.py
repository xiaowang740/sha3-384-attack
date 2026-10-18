#!/usr/bin/env python3
"""Decode one SAT model produced for the Keccak internal-difference CNF."""

import argparse
import json
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
            value = bits_to_int(box["weight_bits"], model)
            boxes.append({"y": box["y"], "z": box["z"], "weight": value})
            total += value
        result.append({
            "transition": item["transition"],
            "boxes": boxes,
            "total_weight": sum(box["weight"] for box in boxes),
            "active_boxes": sum(box["weight"] != 0 for box in boxes),
        })
    return result, total


def lane_values(variables, model):
    return [
        f"{bits_to_int(variables[lane * 32:(lane + 1) * 32], model):08x}"
        for lane in range(25)
    ]


def write_report(path, data, decoded_states, transitions, total):
    report = path.with_suffix(".report.txt")
    with report.open("w", encoding="ascii", newline="\n") as output:
        output.write(f"iota_start_round: {data['iota_start_round']}\n")
        output.write(f"iota_rc_start: {data.get('iota_rc_start', 0)}\n")
        output.write(f"total_weight: {total}\n\n")
        for name in ("a0", "b0", "c0", "a1", "b1", "c1", "a2", "b2", "c2", "b3"):
            values = decoded_states[name]
            output.write(f"{name} (5x5 lanes, 32-bit each):\n")
            for y in range(5):
                output.write("|" + "|".join(values[y * 5:(y + 1) * 5]) + "|\n")
            output.write("\n")
        output.write("weight details:\n")
        for transition in transitions:
            output.write(
                f"transition {transition['transition']}: "
                f"total_weight={transition['total_weight']}, "
                f"active_boxes={transition['active_boxes']}\n"
            )
            for box in transition["boxes"]:
                output.write(
                    f"  y={box['y']:1d} z={box['z']:2d} "
                    f"weight={box['weight']}\n"
                )
            output.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("--weights", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-transition-weight", type=int, default=None)
    args = parser.parse_args()

    model = read_model(args.model)
    data = json.loads(Path(args.weights).read_text(encoding="ascii"))
    path = {"iota_start_round": data["iota_start_round"], "transitions": []}

    decoded_states = {}
    for group in ("path_state_bits", "path_c_bits", "path_a_bits"):
        for name in sorted(data.get(group, {})):
            decoded_states[name] = lane_values(data[group][name], model)
            path[name] = decoded_states[name]

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
    path["transition_weights"] = [item["total_weight"] for item in transitions]
    if "total_weight_bits" in data:
        path["total_weight_bits_lsb_first"] = [
            int(model.get(var, False)) for var in data["total_weight_bits"]
        ]
    Path(args.out).write_text(
        json.dumps(path, indent=2, ensure_ascii=True) + "\n",
        encoding="ascii",
    )
    report = write_report(Path(args.out), data, decoded_states, transitions, total)
    print(f"decoded path: {args.out}")
    print(f"decoded lane/weight report: {report}")
    print(f"total_weight: {total}")
    for transition in transitions:
        active = [
            box for box in transition["boxes"] if box["weight"]
        ]
        print(
            f"transition {transition['transition']}: "
            f"active_boxes={len(active)}, "
            f"weight={sum(box['weight'] for box in active)}"
        )


if __name__ == "__main__":
    main()
