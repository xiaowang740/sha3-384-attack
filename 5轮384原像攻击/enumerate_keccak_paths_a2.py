#!/usr/bin/env python3
"""Enumerate paths for the CNF whose final explicit state is a2."""

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from enumerate_keccak_paths import load_existing_paths, parse_model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--solver", required=True)
    parser.add_argument("--cnf", required=True, type=Path)
    parser.add_argument("--weights", required=True, type=Path)
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--max-transition-weight", type=int, default=None)
    parser.add_argument("--max-total-weight", type=int, default=None)
    parser.add_argument("--combined", default="all_paths.jsonl")
    parser.add_argument("--run-tag", default=None)
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    combined = args.outdir / args.combined
    tag = args.run_tag or time.strftime("%Y%m%d_%H%M%S")
    lines = args.cnf.read_text(encoding="ascii").splitlines()
    variable_count = int(lines[0].split()[2])
    clauses = [line for line in lines[1:] if line.strip()]
    metadata = json.loads(args.weights.read_text(encoding="utf-8"))
    pathvars = [
        (name, metadata["path_state_bits"][name])
        for name in sorted(metadata["path_state_bits"])
    ]

    existing_count = 0
    if not args.fresh:
        existing = load_existing_paths(combined, pathvars)
        clauses.extend(existing)
        existing_count = len(existing)
        if existing_count:
            print(f"Loaded {existing_count} existing a2 paths; excluding them")

    found = 0
    with tempfile.TemporaryDirectory() as temp_dir:
        work_cnf = Path(temp_dir) / "work.cnf"
        for sequence in range(1, args.count + 1):
            work_cnf.write_text(
                "\n".join([f"p cnf {variable_count} {len(clauses)}"] + clauses) + "\n",
                encoding="ascii",
            )
            print(
                f"Running SAT search... ({sequence}/{args.count})",
                flush=True,
            )
            result = subprocess.run(
                [args.solver, str(work_cnf)],
                capture_output=True,
                text=True,
            )
            output = result.stdout + result.stderr
            if result.returncode == 20 or "s UNSATISFIABLE" in output:
                break
            if result.returncode not in (0, 10):
                raise SystemExit(output or f"solver exited with {result.returncode}")
            model = parse_model(output)
            if not model:
                raise SystemExit("solver model not found")

            index = existing_count + sequence
            model_path = args.outdir / f"{tag}_model_{index:03d}.txt"
            path_path = args.outdir / f"{tag}_path_{index:03d}.json"
            model_path.write_text(output, encoding="utf-8")
            decode_command = [
                sys.executable,
                str(Path(__file__).with_name("decode_keccak_path_a2.py")),
                str(model_path),
                "--weights",
                str(args.weights),
                "--out",
                str(path_path),
            ]
            if args.max_transition_weight is not None:
                decode_command += [
                    "--max-transition-weight",
                    str(args.max_transition_weight),
                ]
            if args.max_total_weight is not None:
                decode_command += ["--max-total-weight", str(args.max_total_weight)]
            subprocess.run(decode_command, check=True)
            decoded = json.loads(path_path.read_text(encoding="ascii"))
            with combined.open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps({"index": index, **decoded}, ensure_ascii=True) + "\n"
                )

            block = []
            for _, variables in pathvars:
                block.extend(
                    str(-variable if model.get(variable, False) else variable)
                    for variable in variables
                )
            clauses.append(" ".join(block) + " 0")
            found += 1

    print(f"found {found} new a2 paths; combined file: {combined}")


if __name__ == "__main__":
    main()
