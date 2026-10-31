"""Model through a3 with W0 <= 40 and 2*W1 + 2*W2 + W3 <= 170."""
import argparse
import json
from pathlib import Path

from keccak_ddt_path_sat import (
    Cnf, RC32, IOTA_RC_START, add_iota, exactly_one, linear_rows,
    ddt_table, add_cp_kernel, add_ddt_chi_transition, add_at_most,
)
from keccak_ddt_path_sat_a2 import add_input_weight_lookup


def build(start_round=0, transition0_limit=40, objective_limit=170):
    # Four Iota applications must all fit in the 24-entry RC table.
    start_count = len(RC32) - IOTA_RC_START - 3
    if start_round is not None and not 0 <= start_round < start_count:
        raise ValueError('start_round must be in range(20)')
    if transition0_limit < 0 or objective_limit < 0:
        raise ValueError('weight limits must be non-negative')
    c = Cnf()
    q = [c.var() for _ in range(start_count)]
    exactly_one(c, q)
    if start_round is not None:
        c.clause(q[start_round])
    b = [[c.var() for _ in range(800)] for _ in range(4)]
    c.clause(*b[0])
    meta = {
        'model': 'period-32 Keccak through a3; weighted objective',
        'period_bits': 32, 'lane_indexing': 'x+5*y',
        'linear_z_modulus': 32, 'iota_encoding': 'rc_low32_xor_high32',
        'iota_rc_start': IOTA_RC_START, 'iota_start_round': start_round,
        'start_round_selector_bits': q,
        'cp_kernel_states': ['c1', 'c2'],
        'transition_count': 4, 'explicit_final_state': 'a3',
        'transition0_limit': transition0_limit,
        'objective_coefficients': [0, 2, 2, 1],
        'objective_limit': objective_limit,
        'transition_3_weight_source': 'a3_input_ddt_row',
        'path_state_bits': {f'b{r}': b[r] for r in range(4)},
        'path_a_bits': {}, 'path_c_bits': {},
        'round_transition_weights': [
            {'transition': r, 'boxes': []} for r in range(4)
        ],
    }
    rows, ddt = linear_rows(), ddt_table()
    objective_terms = []
    for r in range(4):
        # add_iota fills this list with constrained XOR output variables.
        c_bits = [None] * 800
        add_iota(c, b[r], c_bits, q, r)
        meta['path_c_bits'][f'c{r}'] = c_bits
        if r in (1, 2):
            add_cp_kernel(c, c_bits)
        a = [c.var() for _ in range(800)]
        meta['path_a_bits'][f'a{r}'] = a
        for out_bit, sources in enumerate(rows):
            c.xor_eq(a[out_bit], (c_bits[src] for src in sources))
        if r < 3:
            add_ddt_chi_transition(c, a, b[r + 1], ddt, r, meta)
        else:
            add_input_weight_lookup(c, a, ddt, r, meta)
        terms = []
        for box in meta['round_transition_weights'][r]['boxes']:
            if box.get('weight_encoding') == 'unary_threshold':
                terms.extend(box['weight_bits'])
            else:
                w0, w1, w2 = box['weight_bits']
                terms.extend([w0] + [w1] * 2 + [w2] * 4)
        if r == 0:
            add_at_most(c, terms, transition0_limit)
        objective_terms.extend(terms * meta['objective_coefficients'][r])
    add_at_most(c, objective_terms, objective_limit)
    return c, meta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--weights', required=True)
    parser.add_argument('--start-round', type=int, choices=range(20), default=0)
    parser.add_argument('--transition0-limit', type=int, default=40)
    parser.add_argument('--objective-limit', type=int, default=170)
    args = parser.parse_args()
    cnf, meta = build(args.start_round, args.transition0_limit, args.objective_limit)
    cnf.write(args.out)
    Path(args.weights).write_text(json.dumps(meta, indent=2) + '\n', encoding='ascii')
    print(f'Wrote {args.out}: {cnf.nvars} variables, {len(cnf.clauses)} clauses')
    print(f'W0 <= {args.transition0_limit}; 2*W1+2*W2+W3 <= {args.objective_limit}')


if __name__ == '__main__':
    main()
