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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--solver', required=True)
    parser.add_argument('--cnf', required=True, type=Path)
    parser.add_argument('--weights', required=True, type=Path)
    parser.add_argument('--outdir', required=True, type=Path)
    parser.add_argument('--count', type=int, default=50)
    parser.add_argument('--threads', type=int, default=2,
                        help='solver threads (default: 2)')
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
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary) / 'work.cnf'
        for sequence in range(1, args.count + 1):
            work.write_text('\n'.join([f'p cnf {nvars} {len(clauses)}'] + clauses) + '\n', encoding='ascii')
            thread_label = args.threads if args.threads is not None else 'solver default'
            print(f'Running SAT search... ({sequence}/{args.count}, threads={thread_label})', flush=True)
            solver_command = [args.solver]
            if args.threads is not None:
                solver_command.append(f'--threads={args.threads}')
            solver_command.append(str(work))
            result = subprocess.run(
                solver_command,
                capture_output=True, text=True,
            )
            output = result.stdout + result.stderr
            if result.returncode == 20 or 's UNSATISFIABLE' in output:
                print('UNSAT: no more paths', flush=True)
                break
            if result.returncode not in (0, 10):
                failure_log = args.outdir / f'{tag}_solver_failure_{sequence:03d}.log'
                code = result.returncode
                status = f'{code} (0x{code & 0xffffffff:08X})'
                failure_log.write_text(
                    f'solver exit code: {status}\n' + output, encoding='utf-8',
                )
                raise SystemExit(
                    f'Solver exited without a result. Exit code: {status}\n'
                    f'Full log saved to: {failure_log}'
                )
            path = decode(meta, parse_model(output))
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
            clauses.append(path_block_clause(path, pathvars))
            found += 1
    print(f'found {found} new paths; combined file: {combined}')


if __name__ == '__main__':
    main()
