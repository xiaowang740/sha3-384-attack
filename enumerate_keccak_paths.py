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

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--solver',required=True); ap.add_argument('--cnf',required=True)
    ap.add_argument('--weights',required=True); ap.add_argument('--outdir',required=True)
    ap.add_argument('--count',type=int,default=10); ap.add_argument('--max-transition-weight',type=int,default=30)
    ap.add_argument('--combined',default='all_paths.jsonl')
    ap.add_argument('--run-tag',default=None)
    a=ap.parse_args(); out=Path(a.outdir); out.mkdir(exist_ok=True)
    combined_path=out/a.combined
    tag=a.run_tag or time.strftime('%Y%m%d_%H%M%S')
    base=Path(a.cnf).read_text(); lines=base.splitlines(); n=int(lines[0].split()[2])
    clauses=[x for x in lines[1:] if x.strip()]; data=json.loads(Path(a.weights).read_text())
    pathvars=[]; found=0
    for name in sorted(data['path_state_bits']): pathvars += data['path_state_bits'][name]
    with tempfile.TemporaryDirectory() as td:
        cnf=Path(td)/'work.cnf'
        for idx in range(1,a.count+1):
            cnf.write_text('\n'.join([f'p cnf {n} {len(clauses)}']+clauses)+'\n')
            r=subprocess.run([a.solver,str(cnf)],capture_output=True,text=True)
            if r.returncode==20 or 's UNSATISFIABLE' in r.stdout or 's UNSATISFIABLE' in r.stderr: break
            if r.returncode not in (0,10): raise SystemExit(r.stderr or r.stdout)
            model=parse_model(r.stdout+r.stderr)
            if not model: raise SystemExit('solver model not found')
            modelpath=out/f'{tag}_model_{idx:03d}.txt'; modelpath.write_text(r.stdout+r.stderr)
            path=data
            pathout=out/f'{tag}_path_{idx:03d}.json'
            subprocess.run([sys.executable, str(Path(__file__).with_name('decode_keccak_path.py')),str(modelpath),'--weights',str(a.weights),'--out',str(pathout),'--max-transition-weight',str(a.max_transition_weight)],check=True)
            decoded=json.loads(pathout.read_text())
            with combined_path.open('a',encoding='utf-8') as stream:
                stream.write(json.dumps({'index':idx,**decoded},ensure_ascii=False)+'\n')
            found=idx
            # Block this exact path assignment; auxiliaries may vary freely.
            block=[]
            for v in pathvars:
                block.append(str(-v if model.get(v,False) else v))
            clauses.append(' '.join(block)+' 0')
        print(f'found {found} paths; combined file: {combined_path}')
if __name__=='__main__': main()
