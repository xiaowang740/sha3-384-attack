#!/usr/bin/env python3
"""Extend 800-bit Keccak paths through the next linear layer and DDT analysis."""

import argparse
import json
import re
from pathlib import Path

from keccak_ddt_path_sat import IOTA_RC_START, RC32, ROT


LANE_REPORT_HEADER = "Keccak path extension: b3 -> c3 -> a3"
STATE_NAMES = ("b0", "c0", "a0", "b1", "c1", "a1", "b2", "c2", "a2", "b3")
LANE_RE = re.compile(r"^\|([0-9a-fA-F]{8}(?:\|[0-9a-fA-F]{8}){4})\|$")


def parse_lane_report(path):
    states = {}
    current = None
    with path.open(encoding="ascii") as stream:
        for line_number, raw_line in enumerate(stream, 1):
            line = raw_line.strip()
            if line.startswith("32-bit lanes ") or line.startswith("Bit z is "):
                continue
            if not line:
                continue
            if line.endswith(":") and line[:-1] in STATE_NAMES:
                current = line[:-1]
                states[current] = []
                continue
            match = LANE_RE.match(line)
            if match:
                if current is None:
                    raise ValueError(f"{path}:{line_number}: lane row has no state")
                states[current].extend(
                    int(value, 16) for value in match.group(1).split("|")
                )
                continue
            if line.startswith("transition ") or line.startswith("total_weight:"):
                continue
            if line == LANE_REPORT_HEADER or line.startswith("extension_"):
                break
            raise ValueError(f"{path}:{line_number}: unrecognized line: {line}")
    missing = [name for name in STATE_NAMES if name not in states]
    if missing:
        raise ValueError(f"{path}: missing states: {', '.join(missing)}")
    for name in STATE_NAMES:
        if len(states[name]) != 25:
            raise ValueError(f"{path}: {name} has {len(states[name])} lanes, expected 25")
    return states


def theta_rho_pi(state):
    columns = [[0] * 32 for _ in range(5)]
    for x in range(5):
        for z in range(32):
            for y in range(5):
                columns[x][z] ^= (state[x + 5 * y] >> z) & 1

    after_theta = [0] * 25
    for x in range(5):
        for y in range(5):
            value = 0
            for z in range(32):
                bit = (
                    ((state[x + 5 * y] >> z) & 1)
                    ^ columns[(x - 1) % 5][z]
                    ^ columns[(x + 1) % 5][(z - 1) % 32]
                )
                value |= bit << z
            after_theta[x + 5 * y] = value

    result = [0] * 25
    for x in range(5):
        for y in range(5):
            destination_x = y
            destination_y = (2 * x + 3 * y) % 5
            rotation = ROT[x][y] % 32
            value = after_theta[x + 5 * y]
            result[destination_x + 5 * destination_y] = (
                value
                if rotation == 0
                else ((value << rotation) | (value >> (32 - rotation))) & 0xFFFFFFFF
            )
    return result


def chi5(value):
    return sum(
        (
            ((value >> x) & 1)
            ^ (((1 ^ ((value >> ((x + 1) % 5)) & 1))
                & ((value >> ((x + 2) % 5)) & 1)))
        )
        << x
        for x in range(5)
    )


def ddt_table():
    table = [[0] * 32 for _ in range(32)]
    for alpha in range(32):
        for value in range(32):
            table[alpha][chi5(value) ^ chi5(value ^ alpha)] += 1
    return table


def analyze_transition(a3, ddt):
    possible_total_weights = {0}
    unique_outputs = 0
    ambiguous_outputs = 0
    unique_weight_boxes = 0
    possible_weights = set()
    for y in range(5):
        for z in range(32):
            alpha = sum(((a3[x + 5 * y] >> z) & 1) << x for x in range(5))
            choices = [count for count in ddt[alpha] if count]
            if not choices:
                raise ValueError(f"no DDT output for y={y}, z={z}, alpha={alpha:02x}")
            choice_weights = {6 - count.bit_length() for count in choices}
            possible_weights.update(choice_weights)
            if len(choices) == 1:
                unique_outputs += 1
            else:
                ambiguous_outputs += 1
            if len(choice_weights) == 1:
                unique_weight_boxes += 1
            possible_total_weights = {
                previous + weight
                for previous in possible_total_weights
                for weight in choice_weights
            }
    return {
        "box_count": 160,
        "unique_output_boxes": unique_outputs,
        "ambiguous_output_boxes": ambiguous_outputs,
        "unique_weight_boxes": unique_weight_boxes,
        "minimum_weight": min(possible_total_weights),
        "maximum_weight": max(possible_total_weights),
        "possible_total_weights": sorted(possible_total_weights),
        "possible_box_weights": sorted(possible_weights),
        "weight_is_unique": len(possible_total_weights) == 1,
    }


def lane_block(name, values):
    lines = [f"{name}:"]
    for y in range(5):
        lines.append("|" + "|".join(f"{value:08x}" for value in values[y * 5:(y + 1) * 5]) + "|")
    lines.append("")
    return "\n".join(lines)


def append_lane_extension(path, c3, a3, analysis, existing_total):
    original = path.read_text(encoding="ascii")
    marker = "\n" + LANE_REPORT_HEADER + "\n"
    if marker in original:
        original = original.split(marker, 1)[0].rstrip() + "\n"
    extension = (
        marker
        + lane_block("c3", c3)
        + lane_block("a3", a3)
        + f"transition 3 (a3 -> b4, b4 not emitted): "
        f"minimum_weight={analysis['minimum_weight']}, "
        f"maximum_weight={analysis['maximum_weight']}, "
        f"unique_output_boxes={analysis['unique_output_boxes']}/160, "
        f"unique_weight_boxes={analysis['unique_weight_boxes']}/160, "
        f"ambiguous_output_boxes={analysis['ambiguous_output_boxes']}/160\n"
        + f"possible_transition_3_weights: "
        f"{analysis['possible_total_weights']}\n"
        + f"existing_total_weight: {existing_total}\n"
        + f"minimum_total_weight_with_transition_3: "
        f"{existing_total + analysis['minimum_weight']}\n"
        + f"transition_3_weight_is_unique: "
        f"{analysis['weight_is_unique']}\n"
    )
    path.write_text(original.rstrip() + extension, encoding="ascii", newline="\n")


def extend_json(path, c3, a3, analysis):
    data = json.loads(path.read_text(encoding="ascii"))
    existing_total = data.get("total_weight")
    data["c3"] = [f"{value:08x}" for value in c3]
    data["a3"] = [f"{value:08x}" for value in a3]
    data["transition_3_analysis"] = analysis
    if isinstance(existing_total, int):
        data["minimum_total_weight_with_transition_3"] = (
            existing_total + analysis["minimum_weight"]
        )
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="ascii")


def process(lanes_path, json_path=None):
    states = parse_lane_report(lanes_path)
    data = {}
    if json_path and json_path.exists():
        data = json.loads(json_path.read_text(encoding="ascii"))
    start_round = data.get("iota_start_round")
    if start_round is None:
        candidates = [
            candidate for candidate in range(len(RC32) - IOTA_RC_START - 2)
            if all(
                states[f"b{stage}"][0] ^ states[f"c{stage}"][0]
                == RC32[IOTA_RC_START + candidate + stage]
                for stage in range(3)
            )
        ]
        if len(candidates) != 1:
            raise ValueError("cannot determine a unique iota start round for extension")
        start_round = candidates[0]
    if not isinstance(start_round, int) or start_round < 0:
        raise ValueError("invalid iota start round for extension")
    round_index = IOTA_RC_START + start_round + 3
    if round_index >= len(RC32):
        raise ValueError("no round constant available for the b3 extension")
    c3 = list(states["b3"])
    c3[0] ^= RC32[round_index]
    a3 = theta_rho_pi(c3)
    analysis = analyze_transition(a3, ddt_table())
    existing_total = 0
    if json_path and json_path.exists():
        existing_total = data.get("total_weight", 0)
        extend_json(json_path, c3, a3, analysis)
    append_lane_extension(lanes_path, c3, a3, analysis, existing_total)
    return analysis, existing_total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, nargs="?")
    parser.add_argument("--directory", type=Path)
    args = parser.parse_args()
    if bool(args.path) == bool(args.directory):
        raise SystemExit("provide exactly one path or --directory")
    if args.directory:
        lane_files = sorted(args.directory.glob("*.lanes.txt"))
    else:
        lane_files = [args.path]
    for lanes_path in lane_files:
        json_path = lanes_path.with_suffix("").with_suffix(".json")
        analysis, total = process(lanes_path, json_path if json_path.exists() else None)
        print(
            f"{lanes_path.name}: existing={total}, "
            f"transition_3_weights={analysis['possible_total_weights']}, "
            f"unique_outputs={analysis['unique_output_boxes']}/160"
        )


if __name__ == "__main__":
    main()
