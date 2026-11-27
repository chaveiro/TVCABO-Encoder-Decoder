"""Generates firmware/encoder.asm from firmware/encoder.tpl (unrolled data-bit emission).
Usage: python3 tools/gen_encoder.py [pad0=11]"""
import sys
PAD0 = int(sys.argv[1]) if len(sys.argv) > 1 else 11
T0 = 131
def tk(k): return T0 + 8*(k % 4) + 31*(k // 4)
def q(k): return 42 + tk(k)
lines = []
cnt=[0]
def pad(n):
    o=""
    if n >= 7: o += "\trcall\tpausar\t; 7 cycles\n"; n -= 7
    for _ in range(n//2):
        cnt[0]+=1; o+=f"\trjmp\tw{cnt[0]}\nw{cnt[0]}:\n"
    if n%2: o+="\tnop\n"
    return o
lines.append(pad(PAD0))
regs = ['datak', 'datav', 'datab']
for k in range(24):
    reg = regs[k // 8]; b = 7 - (k % 8)
    lines.append(f"\tldi\ttemp,dlo\n\tsbrc\t{reg},{b}\n\tldi\ttemp,dhi\n\tout\tPORTD,temp\t; bit {k}\n")
    if k < 23:
        lines.append(pad(q(k+1) - q(k) - 4))
    else:
        lines.append(pad(7))
lines.append("\tout\tPORTD,zonaB\t; back to black\n")
data = ''.join(lines)
import os
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'firmware')
tpl = open(os.path.join(D, 'encoder.tpl')).read()
open(os.path.join(D, 'encoder.asm'), 'w').write(tpl.replace('@@DATA@@', data))
