"""Model through a3 with W0 <= 50 and 2*W1 + 2*W2 + W3 <= 170."""
import argparse
import json
from pathlib import Path

from keccak_ddt_path_sat_a3_weighted import build as build_base


def build(start_round=0, transition0_limit=50, objective_limit=170):
    return build_base(start_round, transition0_limit, objective_limit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--weights', required=True)
    parser.add_argument('--start-round', type=int, choices=range(20), default=0)
    parser.add_argument('--transition0-limit', type=int, default=50)
    parser.add_argument('--objective-limit', type=int, default=170)
    args = parser.parse_args()
    cnf, metadata = build(args.start_round, args.transition0_limit, args.objective_limit)
    cnf.write(args.out)
    Path(args.weights).write_text(json.dumps(metadata, indent=2) + '\n', encoding='ascii')
    print(f'Wrote {args.out}: {cnf.nvars} variables, {len(cnf.clauses)} clauses')
    print(f'W0 <= {args.transition0_limit}; 2*W1+2*W2+W3 <= {args.objective_limit}')


if __name__ == '__main__':
    main()
