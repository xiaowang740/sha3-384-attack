import argparse, json, subprocess, tempfile, time, sys
from pathlib import Path


def parse_model(text):
    vals={}
    for line in text.splitlines():
        if line.startswith('v '):
            for t in line[2:].split():
                v=int(t)
                if v: vals[abs(v)]=v>0
    return vals


def path_block_clause(path, pathvars):
    literals = []
    for name, bits in pathvars:
        lanes = path.get(name)
        if not isinstance(lanes, list) or len(lanes) != 25:
            raise ValueError(f"已有路径缺少有效状态 {name}")
        for lane_index, lane in enumerate(lanes):
            if not isinstance(lane, str) or len(lane) != 8:
                raise ValueError(f"已有路径 {name} 包含无效 lane 值")
            value = int(lane, 16)
            lane_bits = bits[lane_index * 32:(lane_index + 1) * 32]
            if len(lane_bits) != 32:
                raise ValueError(f"已有路径元数据中的 {name} 变量数量不是 800")
            for bit, var in enumerate(lane_bits):
                literals.append(str(-var if value & (1 << bit) else var))
    return ' '.join(literals) + ' 0'


def load_existing_paths(combined_path, pathvars):
    if not combined_path.exists():
        return []
    clauses = []
    with combined_path.open(encoding='utf-8') as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                path = json.loads(line)
                clauses.append(path_block_clause(path, pathvars))
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise SystemExit(
                    f"无法读取已有路径 {combined_path} 第 {line_number} 行：{exc}"
                ) from exc
    return clauses


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--solver',required=True); ap.add_argument('--cnf',required=True)
    ap.add_argument('--weights',required=True); ap.add_argument('--outdir',required=True)
    ap.add_argument('--count',type=int,default=10); ap.add_argument('--max-transition-weight',type=int,default=None)
    ap.add_argument('--max-total-weight',type=int,default=None)
    ap.add_argument('--combined',default='all_paths.jsonl')
    ap.add_argument('--run-tag',default=None)
    ap.add_argument('--fresh',action='store_true',
                    help='ignore existing all_paths.jsonl and start a fresh enumeration')
    a=ap.parse_args(); out=Path(a.outdir); out.mkdir(exist_ok=True)
    combined_path=out/a.combined
    tag=a.run_tag or time.strftime('%Y%m%d_%H%M%S')
    base=Path(a.cnf).read_text(); lines=base.splitlines(); n=int(lines[0].split()[2])
    clauses=[x for x in lines[1:] if x.strip()]; data=json.loads(Path(a.weights).read_text())
    pathvars=[]
    for name in sorted(data['path_state_bits']):
        pathvars.append((name, data['path_state_bits'][name]))
    existing_count = 0
    if not a.fresh:
        existing_clauses = load_existing_paths(combined_path, pathvars)
        clauses.extend(existing_clauses)
        existing_count = len(existing_clauses)
        if existing_count:
            print(f"Loaded {existing_count} existing paths; excluding them")
    found=0
    with tempfile.TemporaryDirectory() as td:
        cnf=Path(td)/'work.cnf'
        for idx in range(1,a.count+1):
            cnf.write_text('\n'.join([f'p cnf {n} {len(clauses)}']+clauses)+'\n')
            r=subprocess.run([a.solver,str(cnf)],capture_output=True,text=True)
            if r.returncode==20 or 's UNSATISFIABLE' in r.stdout or 's UNSATISFIABLE' in r.stderr: break
            if r.returncode not in (0,10): raise SystemExit(r.stderr or r.stdout)
            model=parse_model(r.stdout+r.stderr)
            if not model: raise SystemExit('solver model not found')
            output_idx = existing_count + idx
            modelpath=out/f'{tag}_model_{output_idx:03d}.txt'; modelpath.write_text(r.stdout+r.stderr)
            path=data
            pathout=out/f'{tag}_path_{output_idx:03d}.json'
            decode_args = [
                sys.executable, str(Path(__file__).with_name('decode_keccak_path.py')),
                str(modelpath), '--weights', str(a.weights), '--out', str(pathout),
            ]
            if a.max_transition_weight is not None:
                decode_args += ['--max-transition-weight', str(a.max_transition_weight)]
            if a.max_total_weight is not None:
                decode_args += ['--max-total-weight', str(a.max_total_weight)]
            subprocess.run(decode_args, check=True)
            decoded=json.loads(pathout.read_text())
            with combined_path.open('a',encoding='utf-8') as stream:
                stream.write(json.dumps({'index':output_idx,**decoded},ensure_ascii=False)+'\n')
            found=idx
            # Block this exact path assignment; auxiliaries may vary freely.
            block=[]
            for _, bits in pathvars:
                for v in bits:
                    block.append(str(-v if model.get(v,False) else v))
            clauses.append(' '.join(block)+' 0')
        print(f'found {found} new paths; combined file: {combined_path}')
if __name__=='__main__': main()
