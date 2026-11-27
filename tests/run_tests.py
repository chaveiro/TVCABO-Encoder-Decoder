#!/usr/bin/env python3
"""Emulator test-suite (no hardware!).  Usage: python3 tests/run_tests.py [quick]

Checks: size/stack, keymix == keytool.F for every nonce, and a closed-loop
matrix encoder -> coded waveform -> decoder for standard and keyed modes.
"""
import os, sys, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'sim'))
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
from harness import load, closed_loop, match, FW
from avr import CPU
import keytool

ORIG = os.path.join(HERE, '..', 'sim', 'decoder_original.asm')
QUICK = 'quick' in sys.argv
NFR = 30 if QUICK else 60
fails = []
def check(name, ok, info=''):
    print(('PASS ' if ok else 'FAIL ') + name + ('  ' + info if info else ''))
    if not ok: fails.append(name)

K1 = [0x1A, 0x2B, 0x3C, 0x4D]; K2 = [0x1A, 0x2B, 0x3C, 0x4E]; STD = [0xFF] * 4
enc = {k: load(FW + '/encoder.asm', e) for k, e in (('std', STD), ('K1', K1), ('K2', K2))}
dec = {k: load(FW + '/decoder.asm', e) for k, e in (('std', STD), ('K1', K1), ('K2', K2))}

# 1 ---- size
check('encoder fits 512 words', len(enc['std'].items) <= 512, '%d words' % len(enc['std'].items))
check('decoder fits 512 words', len(dec['std'].items) <= 512, '%d words' % len(dec['std'].items))

# 2 ---- keymix vs python for every nonce
def run_routine(asm, label, reg, n):
    cpu = CPU(asm); cpu.r[reg] = n; cpu.stack.append(0); cpu.pc = asm.labels[label]
    cpu.run(10**6, stop=lambda s: s.pc == 0)
    return cpu.r[reg], cpu.cyc
rnd = random.Random(1)
keys = [K1, K2, STD, [0, 0, 0, 0]] + [[rnd.randrange(256) for _ in range(4)] for _ in range(6)]
bad = 0
for key in keys:
    da = load(FW + '/decoder.asm', key); ea = load(FW + '/encoder.asm', key)
    for n in range(256):
        r, _ = run_routine(da, 'keymix', 17, n)          # decoder: desco -> M
        bad += r != keytool.F(n, key)
        cpu = CPU(ea); cpu.r[26] = n; cpu.stack.append(0); cpu.pc = ea.labels['kmix']
        cpu.run(10**6, stop=lambda s: s.pc == 0)          # encoder: nonce -> rol3(M)
        bad += cpu.r[5] != keytool.encoder_mask(n, key)
check('decoder keymix == keytool.F and encoder kmix == keytool.encoder_mask (%d keys x 256 values)' % len(keys), bad == 0, 'mismatches=%d' % bad)
check('standard key (erased EEPROM) is the identity', all(keytool.F(n, STD) == n for n in range(256)))

# 3 ---- closed loop
def scenario(name, e, d, expect):
    R = closed_loop(enc[e], dec[d], nfr=NFR)
    ok, bad = match(R, 12 * 4e7)
    frac = ok / max(1, ok + bad)
    lock = (R['dcpu'].r[20] >> 7) & 1
    w = max(R['dcpu'].t3 or [0]); we = max(R['ecpu'].t3 or [0])
    info = 'flags ok %d bad %d (%.0f%%) | codif=%d | stack enc %d dec %d | worst TIMER at ISR end dec %d enc %d (limit 124)' % (
        ok, bad, 100 * frac, lock, R['ecpu'].maxdepth, R['dcpu'].maxdepth, w, we)
    if expect == 'decode':
        check(name, bad == 0 and ok >= 8 and w < 124 and R['ecpu'].maxdepth <= 3 and R['dcpu'].maxdepth <= 3, info)
    else:
        check(name + ' (must NOT decode reliably)', frac < 0.6 and w < 124, info)
    return R
scenario('standard enc -> standard dec', 'std', 'std', 'decode')
scenario('keyed enc K1 -> keyed dec K1', 'K1', 'K1', 'decode')
if not QUICK:
    scenario('keyed enc K1 -> standard dec', 'K1', 'std', 'fail')
    scenario('standard enc -> keyed dec K1', 'std', 'K1', 'fail')
    scenario('keyed enc K1 -> keyed dec K2 (1-bit different key)', 'K1', 'K2', 'fail')

# 4 ---- erased-EEPROM decoder == ORIGINAL decoder (bit-exact mux output)
if os.path.exists(ORIG):
    o = load(ORIG)
    Ra = closed_loop(enc['std'], dec['std'], nfr=NFR // 2)
    Rb = closed_loop(enc['std'], o, nfr=NFR // 2)
    f = lambda R: [(round(t), c) for t, c, _ in R['dev'] if t > 10 * 4e7]
    A, B = f(Ra), f(Rb)
    check('patched decoder (std key) output identical to original decoder', A == B and len(A) > 1000, '%d mux edges compared' % len(A))
print('\n%d failure(s)' % len(fails)); sys.exit(1 if fails else 0)
