"""Enumerate paths satisfying the a3 weighted-objective CNF."""
import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

from enumerate_keccak_paths import load_existing_paths, parse_model, path_block_clause
from decode_keccak_path_a3_weighted import decode
from decode_keccak_path import format_lane_report
from incremental_sat_solver import IncrementalSatSolver


def main(default_threads=2):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--solver', required=True)
    parser.add_argument('--cnf', required=True, type=Path)
    parser.add_argument('--weights', required=True, type=Path)
    parser.add_argument('--outdir', required=True, type=Path)
    parser.add_argument('--count', type=int, default=50)
    parser.add_argument('--threads', type=int, default=default_threads,
                        help=f'solver threads (default: {default_threads})')
    parser.add_argument('--run-tag', default=None)
    parser.add_argument('--fresh', action='store_true')
    args = parser.parse_args()
    if args.threads is not None and args.threads < 1:
        parser.error('--threads must be positive')
    meta = json.loads(args.weights.read_text(encoding='ascii'))
    # Include a3 to make resume incompatible with old, unextended result files.
    pathvars = sorted({**meta['path_state_bits'], 'a3': meta['path_a_bits']['a3']}.items())
    lines = args.cnf.read_text(encoding='ascii').splitlines()
    header = next(line for line in lines if line.startswith('p cnf '))
    nvars = int(header.split()[2])
    clauses = [line for line in lines if line.strip() and not line.startswith(('p ', 'c'))]
    args.outdir.mkdir(parents=True, exist_ok=True)
    combined = args.outdir / 'all_paths.jsonl'
    existing = [] if args.fresh else load_existing_paths(combined, pathvars)
    clauses.extend(existing)
    tag = args.run_tag or time.strftime('%Y%m%d_%H%M%S')
    found = 0
    external_options = (
        [f'--threads={args.threads}'] if args.threads is not None else []
    )
    solver = IncrementalSatSolver(
        args.solver, nvars, clauses, args.threads, external_options
    )
    try:
        for sequence in range(1, args.count + 1):
            thread_label = args.threads if args.threads is not None else 'solver default'
            print(f'Running SAT search... ({sequence}/{args.count}, threads={thread_label})', flush=True)
            satisfiable, model, output = solver.solve()
            if not satisfiable:
                print('UNSAT: no more paths', flush=True)
                break
            path = decode(meta, model)
            index = len(existing) + sequence
            prefix = f'{tag}_path_{index:03d}'
            (args.outdir / f'{tag}_model_{index:03d}.txt').write_text(output, encoding='utf-8')
            (args.outdir / f'{prefix}.json').write_text(json.dumps(path, indent=2) + '\n', encoding='ascii')
            report = format_lane_report(path).replace(
                'b3 -> c3 -> a3 -> b4', 'b3 -> c3 -> a3; Chi weight to b4, b4 not modeled')
            report += f"weighted_objective (2*W1+2*W2+W3): {path['weighted_objective']} <= {path['objective_limit']}\n"
            (args.outdir / f'{prefix}.lanes.txt').write_text(report, encoding='ascii')
            print(report, end='', flush=True)
            with combined.open('a', encoding='ascii') as stream:
                stream.write(json.dumps({'index': index, **path}) + '\n')
            solver.add_clause(
                [int(value) for value in path_block_clause(path, pathvars).split()[:-1]]
            )
            found += 1
    finally:
        solver.close()
    print(f'found {found} new paths; combined file: {combined}')


if __name__ == '__main__':
    main()
