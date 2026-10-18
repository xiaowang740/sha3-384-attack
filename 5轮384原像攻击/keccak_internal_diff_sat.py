#!/usr/bin/env python3
"""Build a four-round period-32 Keccak internal-difference reachability CNF.

The initial variable b0 is the output of round 0's chi layer. Thus a
four-round window contains b0, b1, b2, b3 and three cross-round links.
"""

import argparse
from pathlib import Path


RC = (
    0x0000000000000001, 0x0000000000008082,
    0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001,
    0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088,
    0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B,
    0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080,
    0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080,
    0x0000000080000001, 0x8000000080008008,
)
RC32 = tuple((rc & 0xffffffff) ^ (rc >> 32) for rc in RC)

ROT = (
    (0, 36, 3, 41, 18),
    (1, 44, 10, 45, 2),
    (62, 6, 43, 15, 61),
    (28, 55, 25, 21, 56),
    (27, 20, 39, 8, 14),
)


class Cnf:
    def __init__(self):
        self.nvars = 0
        self.clauses = []

    def var(self):
        self.nvars += 1
        return self.nvars

    def clause(self, *lits):
        self.clauses.append(tuple(lits))

    def xor2(self, a, b):
        out = self.var()
        self.clause(a, b, -out)
        self.clause(a, -b, out)
        self.clause(-a, b, out)
        self.clause(-a, -b, -out)
        return out

    def xor_eq(self, target, inputs):
        inputs = list(inputs)
        if not inputs:
            self.clause(-target)
            return
        value = inputs[0]
        for bit in inputs[1:]:
            value = self.xor2(value, bit)
        self.clause(-target, value)
        self.clause(target, -value)

    def xor3_eq_zero(self, a, b, c):
        self.clause(a, b, -c)
        self.clause(a, -b, c)
        self.clause(-a, b, c)
        self.clause(-a, -b, -c)

    def write(self, path):
        with Path(path).open("w", encoding="ascii", newline="\n") as out:
            out.write(f"p cnf {self.nvars} {len(self.clauses)}\n")
            for clause in self.clauses:
                out.write(" ".join(map(str, clause)) + " 0\n")


def rep_index(lane, z):
    return lane * 32 + z


def full_index(x, y, z):
    return (x + 5 * y) * 32 + z


def linear_index(x, y, z):
    return (x + 5 * y) * 32 + z


def theta_rho_pi(state):
    parity = [[0] * 32 for _ in range(5)]
    for x in range(5):
        for z in range(32):
            parity[x][z] = state[full_index(x, 0, z)]
            for y in range(1, 5):
                parity[x][z] ^= state[full_index(x, y, z)]

    theta = [0] * 800
    for x in range(5):
        for y in range(5):
            for z in range(32):
                bit = state[full_index(x, y, z)]
                bit ^= parity[(x - 1) % 5][z]
                bit ^= parity[(x + 1) % 5][(z - 1) % 32]
                theta[full_index(x, y, z)] = bit

    out = [0] * 800
    for x in range(5):
        for y in range(5):
            for z in range(32):
                rz = (z + ROT[x][y]) % 32
                nx, ny = y, (2 * x + 3 * y) % 5
                out[full_index(nx, ny, rz)] = theta[full_index(x, y, z)]
    return out


def theta_rho_pi_32(state):
    parity = [[0] * 32 for _ in range(5)]
    for x in range(5):
        for z in range(32):
            parity[x][z] = state[linear_index(x, 0, z)]
            for y in range(1, 5):
                parity[x][z] ^= state[linear_index(x, y, z)]

    theta = [0] * 800
    for x in range(5):
        for y in range(5):
            for z in range(32):
                bit = state[linear_index(x, y, z)]
                bit ^= parity[(x - 1) % 5][z]
                bit ^= parity[(x + 1) % 5][(z - 1) % 32]
                theta[linear_index(x, y, z)] = bit

    out = [0] * 800
    for x in range(5):
        for y in range(5):
            for z in range(32):
                rz = (z + ROT[x][y]) % 32
                nx, ny = y, (2 * x + 3 * y) % 5
                out[linear_index(nx, ny, rz)] = theta[linear_index(x, y, z)]
    return out


def build_linear_rows():
    # A canonical representative has only its low 32 slices populated.
    rows = [[] for _ in range(800)]
    for src in range(800):
        state = [0] * 800
        lane, z = divmod(src, 32)
        state[linear_index(lane % 5, lane // 5, z)] = 1
        transformed = theta_rho_pi_32(state)
        for lane_out in range(25):
            for z_out in range(32):
                if transformed[linear_index(lane_out % 5, lane_out // 5, z_out)]:
                    rows[rep_index(lane_out, z_out)].append(src)
    return rows


def add_exactly_one(cnf, variables):
    cnf.clause(*variables)
    for i in range(len(variables)):
        for j in range(i + 1, len(variables)):
            cnf.clause(-variables[i], -variables[j])


def add_iota_linear(cnf, b, a_next, q, round_offset, rows):
    mapped = [None] * 800
    for lane in range(25):
        for z in range(32):
            selected_rc = cnf.var()
            selectors = []
            for start, selector in enumerate(q):
                rc = RC32[start + round_offset]
                lane00_bit = (rc >> z) & 1
                if lane == 0 and lane00_bit:
                    selectors.append(selector)
            if selectors:
                cnf.clause(-selected_rc, *selectors)
                for selector in selectors:
                    cnf.clause(-selector, selected_rc)
            else:
                cnf.clause(-selected_rc)
            mapped[rep_index(lane, z)] = cnf.xor2(
                b[rep_index(lane, z)], selected_rc)

    for out_bit, source_bits in enumerate(rows):
        cnf.xor_eq(a_next[out_bit], (mapped[src] for src in source_bits))


def add_chi_class_transition(cnf, a, b):
    state = [cnf.var() for _ in range(800)]
    chi_out = [cnf.var() for _ in range(800)]

    # The witness state is the 800-bit period-32 representative a.
    for lane in range(25):
        for z in range(32):
            state_bit = state[rep_index(lane, z)]
            a_bit = a[rep_index(lane, z)]
            cnf.clause(-state_bit, a_bit)
            cnf.clause(state_bit, -a_bit)

    # Truth-table encoding of 32-bit-period Chi, one 5-bit row at a time.
    for y in range(5):
        for z in range(32):
            inputs = [
                state[rep_index(5 * x + y, z)]
                for x in range(5)
            ]
            outputs = [
                chi_out[rep_index(5 * x + y, z)]
                for x in range(5)
            ]
            for word in range(32):
                xbits = [(word >> x) & 1 for x in range(5)]
                chi = [
                    xbits[x] ^ ((1 ^ xbits[(x + 1) % 5]) & xbits[(x + 2) % 5])
                    for x in range(5)
                ]
                for x in range(5):
                    clause = [
                        -inputs[i] if xbits[i] else inputs[i]
                        for i in range(5)
                    ]
                    clause.append(outputs[x] if chi[x] else -outputs[x])
                    cnf.clause(*clause)

    # The chi output is the 800-bit period-32 representative b.
    for lane in range(25):
        for z in range(32):
            chi_bit = chi_out[rep_index(lane, z)]
            b_bit = b[rep_index(lane, z)]
            cnf.clause(-chi_bit, b_bit)
            cnf.clause(chi_bit, -b_bit)


def build_formula(start_round):
    cnf = Cnf()
    rows = build_linear_rows()
    q = [cnf.var() for _ in range(21)]
    add_exactly_one(cnf, q)
    if start_round is not None:
        cnf.clause(q[start_round])

    # b0 is the first-round chi output; b3 is the fourth-round chi output.
    b = [[cnf.var() for _ in range(800)] for _ in range(4)]
    # Exclude the all-zero start boundary.
    cnf.clause(*b[0])

    for r in range(3):
        a_next = [cnf.var() for _ in range(800)]
        add_iota_linear(cnf, b[r], a_next, q, r, rows)
        add_chi_class_transition(cnf, a_next, b[r + 1])
    return cnf


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="sha3_384_4round_internal_diff.cnf")
    parser.add_argument(
        "--start-round",
        type=int,
        choices=range(21),
        help="fix the first iota round (0..20); default searches all windows",
    )
    args = parser.parse_args()

    cnf = build_formula(args.start_round)
    cnf.write(args.out)
    print(f"Wrote {args.out}: {cnf.nvars} variables, {len(cnf.clauses)} clauses")
    print("Model: four existential period-32 internal-difference transitions from b0.")
    print("This CNF encodes reachability, not DCT/VDCT transition probabilities.")


if __name__ == "__main__":
    main()
