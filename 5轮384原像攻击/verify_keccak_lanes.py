#!/usr/bin/env python3
"""Verify a 3-transition Keccak path from a 25-lane x 32-bit lane dump."""

import argparse
import re
from pathlib import Path

from keccak_ddt_path_sat import IOTA_RC_START, RC32, ROT


STATE_NAMES = ("b0", "c0", "a0", "b1", "c1", "a1", "b2", "c2", "a2", "b3")
LANE_RE = re.compile(r"^\|([0-9a-fA-F]{8}(?:\|[0-9a-fA-F]{8}){4})\|$")


def parse_lanes(path):
    states = {}
    current = None
    with Path(path).open(encoding="ascii") as stream:
        for line_number, raw_line in enumerate(stream, 1):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("32-bit lanes ") or line.startswith("Bit z is "):
                continue
            if line.endswith(":") and line[:-1] in STATE_NAMES:
                current = line[:-1]
                states[current] = []
                continue
            match = LANE_RE.match(line)
            if match:
                if current is None:
                    raise ValueError(f"{path}:{line_number}: lane row has no state header")
                states[current].extend(int(value, 16) for value in match.group(1).split("|"))
                continue
            if line.startswith("transition ") or line.startswith("total_weight:"):
                continue
            raise ValueError(f"{path}:{line_number}: unrecognized line: {line}")

    missing = [name for name in STATE_NAMES if name not in states]
    if missing:
        raise ValueError(f"missing states: {', '.join(missing)}")
    for name in STATE_NAMES:
        if len(states[name]) != 25:
            raise ValueError(f"{name} must contain 25 lanes, got {len(states[name])}")
    return states


def lane_bit(value, z):
    return (value >> z) & 1


def theta_rho_pi(state):
    columns = [[0] * 32 for _ in range(5)]
    for x in range(5):
        for z in range(32):
            for y in range(5):
                columns[x][z] ^= lane_bit(state[x + 5 * y], z)

    after_theta = [0] * 25
    for x in range(5):
        for y in range(5):
            value = 0
            for z in range(32):
                bit = (
                    lane_bit(state[x + 5 * y], z)
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
                ((value << rotation) | (value >> (32 - rotation))) & 0xFFFFFFFF
                if rotation
                else value
            )
    return result


def iota(state, transition):
    result = list(state)
    result[0] ^= RC32[IOTA_RC_START + transition]
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


def transition_weights(a, b, ddt):
    weights = []
    for y in range(5):
        for z in range(32):
            alpha = sum(lane_bit(a[x + 5 * y], z) << x for x in range(5))
            beta = sum(lane_bit(b[x + 5 * y], z) << x for x in range(5))
            count = ddt[alpha][beta]
            if count == 0:
                raise ValueError(
                    f"invalid Chi DDT transition at y={y}, z={z}: "
                    f"alpha=0b{alpha:05b}, beta=0b{beta:05b}"
                )
            weights.append(6 - count.bit_length())
    return weights


def equal_state(left, right):
    return all(a == b for a, b in zip(left, right))


def main():
    parser = argparse.ArgumentParser(
        description="Verify a 3-transition, 800-bit Keccak differential path"
    )
    parser.add_argument("lanes", type=Path)
    parser.add_argument("--start-round", type=int, default=0)
    parser.add_argument("--transition-limits", default="25,20,20")
    parser.add_argument("--total-weight-limit", type=int, default=65)
    args = parser.parse_args()

    states = parse_lanes(args.lanes)
    limits = [int(value) for value in args.transition_limits.split(",")]
    if len(limits) != 3:
        raise SystemExit("--transition-limits must contain three values")
    ddt = ddt_table()

    for transition in range(3):
        expected_c = iota(states[f"b{transition}"], args.start_round + transition)
        if not equal_state(expected_c, states[f"c{transition}"]):
            raise SystemExit(f"FAIL: c{transition} != Iota(b{transition})")
        expected_a = theta_rho_pi(states[f"c{transition}"])
        if not equal_state(expected_a, states[f"a{transition}"]):
            raise SystemExit(f"FAIL: a{transition} != Theta-Rho-Pi(c{transition})")

    weights = []
    for transition in range(3):
        values = transition_weights(
            states[f"a{transition}"], states[f"b{transition + 1}"], ddt
        )
        total = sum(values)
        weights.append(total)
        if total > limits[transition]:
            raise SystemExit(
                f"FAIL: transition {transition} weight {total} > limit {limits[transition]}"
            )
        active = sum(value != 0 for value in values)
        print(
            f"transition {transition}: weight={total}, "
            f"active_boxes={active}, limit={limits[transition]}"
        )

    total = sum(weights)
    if total > args.total_weight_limit:
        raise SystemExit(
            f"FAIL: total weight {total} > limit {args.total_weight_limit}"
        )
    print(f"total_weight: {total}, limit={args.total_weight_limit}")
    print("PASS: RC1 3-transition path is valid in 25 lanes x 32 bits (800 bits)")


if __name__ == "__main__":
    main()
