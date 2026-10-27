#!/usr/bin/env python3
"""Decode an a2-terminal SAT model."""

import argparse
import json
from pathlib import Path

from decode_keccak_path import bits_to_int, decode_weights, read_model


def format_lane_report(path):
    lines = [
        "32-bit lanes (8 hex digits); lane index = x + 5*y; rows y=0..4, columns x=0..4",
        "Bit z is bit (1 << z) of each lane.",
        "",
    ]
    names = [name for name in path if name and name[0] in "abc" and name[1:].isdigit()]
    for name in sorted(
        names,
        key=lambda value: (
            int(value[1:]),
            {"b": 0, "c": 1, "a": 2}[value[0]],
        ),
    ):
        lines.append(f"{name}:")
        for y in range(5):
            lines.append("|" + "|".join(path[name][y * 5:(y + 1) * 5]) + "|")
        lines.append("")
    for transition in path["transitions"]:
        active = sum(bool(box["weight"]) for box in transition["boxes"])
        r = transition["transition"]
        stages = f"b{r} -> c{r} -> a{r}"
        if r != 2:
            stages += f" -> b{r + 1}"
        lines.append(
            f"transition {r} ({stages}): "
            f"weight={transition['weight']}, active_boxes={active}"
        )
    lines.append(f"total_weight: {path['total_weight']}")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("--weights", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--max-transition-weight", type=int, default=None)
    parser.add_argument("--max-total-weight", type=int, default=None)
    args = parser.parse_args()

    model = read_model(args.model)
    data = json.loads(args.weights.read_text(encoding="utf-8"))
    path = {"iota_start_round": data["iota_start_round"], "transitions": []}

    state_bits = {
        **data.get("path_a_bits", {}),
        **data.get("path_c_bits", {}),
        **data["path_state_bits"],
    }
    for name in sorted(state_bits):
        variables = state_bits[name]
        if len(variables) != 800:
            raise ValueError(f"{name}: expected 800 variables")
        path[name] = [
            f"{bits_to_int(variables[lane * 32:(lane + 1) * 32], model):08x}"
            for lane in range(25)
        ]

    transitions, total = decode_weights(data, model)
    if args.max_transition_weight is not None:
        invalid = [
            item for item in transitions if item["weight"] > args.max_transition_weight
        ]
        if invalid:
            raise SystemExit(
                "transition weight limit exceeded: "
                + ", ".join(f"{item['transition']}={item['weight']}" for item in invalid)
            )
    if args.max_total_weight is not None and total > args.max_total_weight:
        raise SystemExit(f"total weight limit exceeded: {total}>{args.max_total_weight}")

    path["transitions"] = transitions
    path["total_weight"] = total
    args.out.write_text(
        json.dumps(path, indent=2, ensure_ascii=True) + "\n",
        encoding="ascii",
    )
    report = format_lane_report(path)
    args.out.with_suffix(".lanes.txt").write_text(report, encoding="ascii")
    print(f"decoded path: {args.out}")
    print(f"lane view: {args.out.with_suffix('.lanes.txt')}")
    print(report, end="", flush=True)


if __name__ == "__main__":
    main()
