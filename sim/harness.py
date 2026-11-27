"""Closed-loop emulation: encoder firmware -> coded waveform -> decoder firmware.

Everything is a software model (AVR emulator + analog model of the board);
it is NOT a hardware test.  See ../tests/run_tests.py.
"""
import os
import numpy as np
from avr import Asm, CPU
from sig import clean_pal, RES, FRAME

TH = 0.15
HERE = os.path.dirname(os.path.abspath(__file__))
FW = os.path.join(HERE, '..', 'firmware')


def load(path, eeprom=None):
    """Assemble a firmware file (relative includes resolved next to it)."""
    a = Asm(open(path).read(), base=os.path.dirname(path))
    if eeprom is not None:
        a.eeprom = list(eeprom) + [0xFF] * (64 - len(eeprom))
    return a


def track_t3(cpu, asm, first):
    """Record TIMER count at label t3 after label `first` (data ISR). Limit is 124."""
    w = []; st = {}
    o1 = cpu.prog[asm.labels[first]]
    def h1(): st['in'] = True; return o1()
    cpu.prog[asm.labels[first]] = h1
    o2 = cpu.prog[asm.labels['t3']]
    def h2():
        if st.get('in'): w.append(cpu.tcnt); st['in'] = False
        return o2()
    cpu.prog[asm.labels['t3']] = h2
    return w


def install_hooks(cpu, asm, hooks):
    """hooks: {label: fn(cpu)} - fn is called when execution reaches the label."""
    for lab, fn in (hooks or {}).items():
        o = cpu.prog[asm.labels[lab]]
        def mk(fn, o):
            def h(): fn(cpu); return o()
            return h
        cpu.prog[asm.labels[lab]] = mk(fn, o)


def run_encoder(asm, sig, offs, ncycles, e0=0.0, d=40e-6, hooks=None):
    N = len(sig); ev = []
    def comp(c):
        t = (c.t + offs) % FRAME
        return 1 if sig[int(t / RES) % N] >= TH else 0
    def eps(c): return e0 + (-d if (c.portb >> 3) & 1 else d)
    def on_out(port, v, c):
        if port == 'D': ev.append((c.t + 100.0, v & 0x38, c.cyc))
    cpu = CPU(asm, comp=comp, tw=0, eps_fn=eps, on_out=on_out)
    flags = []
    dl = asm.labels['dline']; od = cpu.prog[dl]
    def hk():
        flags.append((cpu.cyc, cpu.r[20] & 3)); return od()
    cpu.prog[dl] = hk
    cpu.t3 = track_t3(cpu, asm, 'dline')
    install_hooks(cpu, asm, hooks)
    cpu.run(ncycles)
    return cpu, ev, flags


def build_wave(ev, sig, tmax, offs):
    n = int(tmax / RES) + 1; N = len(sig)
    out = np.full(n, 0.3, dtype=np.float32)
    ev = [e for e in ev if e[0] < tmax]
    for i, (t, code, _) in enumerate(ev):
        t2 = ev[i + 1][0] if i + 1 < len(ev) else tmax
        s = int(t / RES); e = int(t2 / RES)
        if e <= s: continue
        if code == 0x08: lv = 0.3
        elif code == 0x28: lv = 0.0
        else:
            idx = ((np.arange(s, e) * RES + offs) / RES).astype(np.int64) % N
            x = sig[idx]
            lv = x if code == 0x00 else (1.3 - x)
        out[s:e] = lv
    return out


def run_decoder(asm, wave, offs, ncycles, e0=0.0, d=40e-6, hooks=None):
    Nw = len(wave); dev = []
    def comp(c):
        i = int((c.t + offs) / RES)
        return 1 if (i >= Nw or wave[i] >= TH) else 0
    def eps(c): return e0 + (-d if (c.portb >> 3) & 1 else d)
    def don(port, v, c):
        if port == 'D': dev.append((c.t + 100.0, v & 0x38, c.cyc))
    cpu = CPU(asm, comp=comp, tw=0, eps_fn=eps, on_out=don)
    flags = []
    a8 = asm.labels['aux4']; o8 = cpu.prog[a8]
    def h8():
        flags.append((cpu.cyc, cpu.r[20] & 3, (cpu.r[20] >> 7) & 1)); return o8()
    cpu.prog[a8] = h8
    cpu.t3 = track_t3(cpu, asm, 'ldata')
    install_hooks(cpu, asm, hooks)
    cpu.run(ncycles)
    return cpu, dev, flags


def closed_loop(enc, dec, nfr=24, offs_e=12345.0, offs_d=777.0, e0=0.0, ehooks=None, dhooks=None):
    """enc/dec: Asm objects.  Returns dict with logs."""
    sig = clean_pal()
    ecpu, ev, eflags = run_encoder(enc, sig, offs_e, 400000 * nfr, e0=e0, hooks=ehooks)
    tmax = ecpu.t - 1000
    wave = build_wave(ev, sig, tmax, offs_e)
    dcpu, dev, dflags = run_decoder(dec, wave, offs_d, int(tmax / 100) - 2000, e0=e0, hooks=dhooks)
    return dict(ecpu=ecpu, dcpu=dcpu, ev=ev, eflags=eflags, dflags=dflags, dev=dev, wave=wave, sig=sig, offs_e=offs_e, offs_d=offs_d)


def match(R, t_from=18 * 4e7):
    """Compare decoded (video,burst) flags with what the encoder sent."""
    ef = [(c * 100.0, v) for c, v in R['eflags']]
    ok = bad = 0
    for c, v, codif in R['dflags']:
        t = c * 100.0
        if t < t_from: continue
        j = min(range(len(ef)), key=lambda i: abs(ef[i][0] - t))
        if abs(ef[j][0] - t) > 3e5: continue
        if codif == 1 and ef[j][1] == v: ok += 1
        else: bad += 1
    return ok, bad
