#!/usr/bin/env python3
import argparse, json
from pathlib import Path

def at_most(clauses, lits, k, newvar):
    # Sinz sequential counter: s[i][j] means at least j true literals
    # among lits[0:i+1]. The final overflow clause forbids k+1.
    if k < 0:
        clauses.append(())
        return newvar
    if len(lits) <= k:
        return newvar
    if k == 0:
        clauses.extend((-x,) for x in lits)
        return newvar
    s = [[0] * k for _ in lits]
    for i in range(len(lits) - 1):
        for j in range(k):
            s[i][j] = newvar
            newvar += 1
    clauses.append((-lits[0], s[0][0]))
    for i in range(1, len(lits) - 1):
        clauses.append((-lits[i], s[i][0]))
        clauses.append((-s[i-1][0], s[i][0]))
        for j in range(1, k):
            clauses.append((-s[i-1][j], s[i][j]))
            clauses.append((-lits[i], -s[i-1][j-1], s[i][j]))
        clauses.append((-lits[i], -s[i-1][k-1]))
    clauses.append((-lits[-1], -s[-2][k-1]))
    return newvar

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cnf', required=True); ap.add_argument('--weights', required=True)
    ap.add_argument('--out', required=True); ap.add_argument('--limit', type=int, default=30)
    a=ap.parse_args()
    lines=Path(a.cnf).read_text().splitlines(); head=lines[0].split()
    nvars=int(head[2]); clauses=[]
    for line in lines[1:]:
        if line.strip(): clauses.append(tuple(map(int,line.split()[:-1])))
    data=json.loads(Path(a.weights).read_text());
    for tr in data['round_transition_weights']:
        items=[]
        for box in tr['boxes']:
            w2,w1,w0=box['weight_bits']
            # forbid invalid encodings 001,101,110,111
            clauses += [(-w2,-w1,w0), (-w2,w1,-w0), (w2,-w1,-w0), (w2,-w1,w0)]
            # For the allowed codes 000, 010, 011, 100, the numeric
            # value 4*w2+2*w1+w0 equals the Hamming weight of this multiset.
            items += [w2, w2, w2, w2, w1, w1, w0]
        nvars=at_most(clauses, items, a.limit, nvars+1)-1
    out=[f'p cnf {nvars} {len(clauses)}']+[" ".join(map(str,c))+" 0" for c in clauses]
    Path(a.out).write_text('\n'.join(out)+'\n')
if __name__=='__main__': main()
