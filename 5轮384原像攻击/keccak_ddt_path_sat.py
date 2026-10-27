#!/usr/bin/env python3
"""Build a period-32 Keccak differential-path CNF using Chi's 5-bit DDT."""
import argparse
import json
from pathlib import Path

RC = (
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A,
    0x8000000080008000, 0x000000000000808B, 0x0000000080000001,
    0x8000000080008081, 0x8000000000008009, 0x000000000000008A,
    0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
    0x8000000000008003, 0x8000000000008002, 0x8000000000000080,
    0x000000000000800A, 0x800000008000000A, 0x8000000080008081,
    0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
)
RC32 = tuple((rc & 0xffffffff) ^ (rc >> 32) for rc in RC)
TRANSITION_WEIGHT_LIMITS = (25, 20, 20)
TOTAL_WEIGHT_LIMIT = 65
IOTA_RC_START = 1
ROT = ((0,36,3,41,18),(1,44,10,45,2),(62,6,43,15,61),
       (28,55,25,21,56),(27,20,39,8,14))

class Cnf:
    def __init__(self): self.nvars=0; self.clauses=[]
    def var(self): self.nvars+=1; return self.nvars
    def clause(self,*xs): self.clauses.append(tuple(xs))
    def xor2(self,a,b):
        o=self.var(); self.clause(a,b,-o); self.clause(a,-b,o)
        self.clause(-a,b,o); self.clause(-a,-b,-o); return o
    def xor_eq(self,t,ins):
        ins=list(ins)
        if not ins: self.clause(-t); return
        v=ins[0]
        for x in ins[1:]: v=self.xor2(v,x)
        self.clause(-t,v); self.clause(t,-v)
    def write(self,path):
        with Path(path).open('w',encoding='ascii',newline='\n') as f:
            f.write(f'p cnf {self.nvars} {len(self.clauses)}\n')
            for c in self.clauses: f.write(' '.join(map(str,c))+' 0\n')

def ri(l,z): return 32*l+z
def fi(x,y,z): return (x+5*y)*32+z

def theta_rho_pi(s):
    c=[[0]*32 for _ in range(5)]
    for x in range(5):
        for z in range(32):
            for y in range(5): c[x][z]^=s[fi(x,y,z)]
    t=[0]*800
    for x in range(5):
        for y in range(5):
            for z in range(32):
                t[fi(x,y,z)]=s[fi(x,y,z)]^c[(x-1)%5][z]^c[(x+1)%5][(z-1)%32]
    out=[0]*800
    for x in range(5):
        for y in range(5):
            for z in range(32):
                nx,ny=y,(2*x+3*y)%5
                out[fi(nx,ny,(z+ROT[x][y])%32)]=t[fi(x,y,z)]
    return out

def linear_rows():
    rows=[[] for _ in range(800)]
    for src in range(800):
        s=[0]*800; lane,z=divmod(src,32); s[fi(lane%5,lane//5,z)]=1
        o=theta_rho_pi(s)
        for lane2 in range(25):
            for z2 in range(32):
                if o[fi(lane2%5,lane2//5,z2)]:
                    rows[ri(lane2,z2)].append(src)
    return rows

def exactly_one(c,vs):
    c.clause(*vs)
    for i in range(len(vs)):
        for j in range(i+1,len(vs)): c.clause(-vs[i],-vs[j])

def add_cp_kernel(c, state):
    # For every z, each x-column has even parity across y=0..4.
    for z in range(32):
        for x in range(5):
            variables = [state[ri(x + 5 * y, z)] for y in range(5)]
            for odd_mask in range(32):
                if bin(odd_mask).count("1") % 2 == 1:
                    c.clause(*(
                        -variable if (odd_mask >> i) & 1 else variable
                        for i, variable in enumerate(variables)
                    ))

def add_iota(c,b,out,q,offset):
    m=[None]*800
    for lane in range(25):
        for z in range(32):
            sel=c.var(); choices=[]
            for start,qv in enumerate(q):
                rc=RC32[IOTA_RC_START+start+offset]
                if lane==0 and ((rc>>z)&1): choices.append(qv)
            if choices:
                c.clause(-sel,*choices)
                for qv in choices: c.clause(-qv,sel)
            else: c.clause(-sel)
            m[ri(lane,z)]=c.xor2(b[ri(lane,z)],sel)
    for lane in range(25):
        for z in range(32):
            out[ri(lane,z)] = m[ri(lane,z)]

def chi5(v):
    return sum((((v>>x)&1)^((1^((v>>((x+1)%5))&1))&((v>>((x+2)%5))&1)))<<x for x in range(5))

def ddt_table():
    d=[[0]*32 for _ in range(32)]
    for a in range(32):
        for x in range(32): d[a][chi5(x)^chi5(x^a)]+=1
    return d

def forbid_pair(c,ins,outs,a,b):
    # Clause false exactly when ins encodes a and outs encodes b.
    lits=[]
    for i,v in enumerate(ins): lits.append(-v if (a>>i)&1 else v)
    for i,v in enumerate(outs): lits.append(-v if (b>>i)&1 else v)
    c.clause(*lits)

def add_ddt_chi_transition(c,a_bits,b_bits,ddt,transition,meta):
    # Each (y,z) is one independent 5-bit Chi box; its input/output
    # difference bits are the corresponding lane bits in a and b.
    for y in range(5):
        for z in range(32):
            ins=[a_bits[ri(x+5*y,z)] for x in range(5)]
            outs=[b_bits[ri(x+5*y,z)] for x in range(5)]
            w0,w1,w2=[c.var() for _ in range(3)] # metadata is LSB-first
            meta['round_transition_weights'][transition]['boxes'].append(
                {'y':y,'z':z,'weight_bits':[w0,w1,w2]})
            # Allowed DDT entries: 32->0, 16->1, 8->2, 4->3, 2->4.
            for av in range(32):
                for bv in range(32):
                    count=ddt[av][bv]
                    if count==0:
                        forbid_pair(c,ins,outs,av,bv)
                    else:
                        weight=6-count.bit_length() # log2(32/count), counts are powers of two
                        # Condition (input=a AND output=b) implies exact code.
                        cond=[]
                        cond.extend((-ins[i] if (av>>i)&1 else ins[i]) for i in range(5))
                        cond.extend((-outs[i] if (bv>>i)&1 else outs[i]) for i in range(5))
                        bits=((weight>>2)&1,(weight>>1)&1,weight&1)
                        for var,bit in zip((w2,w1,w0),bits): c.clause(*cond,(var if bit else -var))
            # Exclude codes 5..7; every reachable DDT weight is 0..4.
            c.clause(w2,w1,-w0)    # forbid 001
            c.clause(-w2,w1,-w0)   # forbid 101
            c.clause(-w2,-w1,w0)   # forbid 110
            c.clause(-w2,-w1,-w0)  # forbid 111

def add_at_most(c,lits,k):
    n=len(lits)
    if k>=n: return
    if k<0: c.clause(); return
    if k==0:
        for x in lits: c.clause(-x)
        return
    # Sinz sequential counter; s[i][j] means at least j true among prefix 0..i.
    s=[[c.var() for _ in range(k)] for _ in range(n-1)]
    c.clause(-lits[0],s[0][0])
    for i in range(1,n-1):
        c.clause(-lits[i],s[i][0]); c.clause(-s[i-1][0],s[i][0])
        for j in range(1,k):
            c.clause(-s[i-1][j],s[i][j])
            c.clause(-lits[i],-s[i-1][j-1],s[i][j])
        c.clause(-lits[i],-s[i-1][k-1])
    c.clause(-lits[-1],-s[-1][k-1])

def build(start_round,limit,transition_limits=None,total_weight_limit=TOTAL_WEIGHT_LIMIT):
    if limit < 0:
        raise ValueError("limit must be non-negative")
    if transition_limits is None:
        transition_limits = list(TRANSITION_WEIGHT_LIMITS)
    if len(transition_limits) != 3 or any(value < 0 for value in transition_limits):
        raise ValueError("transition_limits must contain three non-negative values")
    if total_weight_limit < 0:
        raise ValueError("total_weight_limit must be non-negative")
    c=Cnf(); rows=linear_rows(); ddt=ddt_table()
    q=[c.var() for _ in range(21)]; exactly_one(c,q)
    if start_round is not None: c.clause(q[start_round])
    b=[[c.var() for _ in range(800)] for _ in range(4)]; c.clause(*b[0])
    meta={'model':'period-32 Keccak differential path with Chi DDT weights',
            'lane_indexing':'x+5*y',
            'period_bits':32,
            'linear_z_modulus':32,
            'iota_encoding':'rc_low32_xor_high32',
              'cp_kernel_states':['c1','c2'],
              'weight_limit_scope':'per_transition_and_total',
              'transition_weight_limits':list(transition_limits),
              'total_weight_limit':total_weight_limit,
              'iota_rc_start':IOTA_RC_START,
          'iota_start_round':start_round,'transition_count':3,
          'weight_definition':'-log2(DDT/32); DDT 32,16,8,4,2 => weight 0,1,2,3,4',
          'weight_encoding':{'bits_lsb_first':['w0','w1','w2'],
                             '0':'000','1':'001','2':'010','3':'011','4':'100'},
          'chi_ddt_nonzero_counts':sorted({v for row in ddt for v in row if v}),
          'round_transition_weights':[{'transition':r,'boxes':[]} for r in range(3)],
          'path_a_bits': {},
          'path_c_bits': {},
          'path_state_bits':{f'b{r}':b[r] for r in range(4)}}
    total_terms = []
    for r in range(3):
        a=[c.var() for _ in range(800)]
        meta['path_a_bits'][f'a{r}'] = a
        c_bits=[c.var() for _ in range(800)]
        meta['path_c_bits'][f'c{r}'] = c_bits
        add_iota(c,b[r],c_bits,q,r)
        if r in (1, 2):
            add_cp_kernel(c, c_bits)
        for out_bit, source_bits in enumerate(rows):
            c.xor_eq(a[out_bit], (c_bits[src] for src in source_bits))
        add_ddt_chi_transition(c,a,b[r+1],ddt,r,meta)
        # Sum each local integer weight using its binary bit multiplicities.
        terms=[]
        for box in meta['round_transition_weights'][r]['boxes']:
            w0,w1,w2=box['weight_bits']; terms += [w2]*4+[w1]*2+[w0]
        total_terms.extend(terms)
        add_at_most(c,terms,transition_limits[r])
    add_at_most(c,total_terms,total_weight_limit)
    meta['max_transition_weight']=max(transition_limits)
    return c,meta

def main():
    p=argparse.ArgumentParser(); p.add_argument('--out',required=True)
    p.add_argument('--weights',required=True); p.add_argument('--limit',type=int,default=30)
    p.add_argument('--transition-limits',default='25,20,20')
    p.add_argument('--total-weight-limit',type=int,default=TOTAL_WEIGHT_LIMIT)
    p.add_argument('--start-round',type=int,choices=range(21),default=None)
    a=p.parse_args()
    limits=[int(value) for value in a.transition_limits.split(',')]
    c,m=build(a.start_round,a.limit,limits,a.total_weight_limit); c.write(a.out)
    Path(a.weights).write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
    print(f'Wrote {a.out}: {c.nvars} variables, {len(c.clauses)} clauses')
    print(f'Wrote {a.weights}; transition limits = {limits}; total weight <= {a.total_weight_limit}')

if __name__=='__main__': main()
