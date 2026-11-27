"""Mini assembler + cycle-accurate emulator for the AT90S1200 subset used here."""
import re, math

import os
class Asm:
    def __init__(s, text, base='.'):
        s.equ = {'exp2': None}; s.defs = {}; s.labels = {}; s.prog = []; s.lines=[]
        s.eeprom = [0xFF] * 64; s.base = base
        s.parse(s.preprocess(text))
    def preprocess(s, text):
        out = []
        for l in text.splitlines():
            m = re.match(r'^\s*\.include\s+"([^"]+)"', l, re.I)
            if m:
                out.extend(s.preprocess(open(os.path.join(s.base, m.group(1))).read()).splitlines())
            else:
                out.append(l)
        return '\n'.join(out)
    def clean(s, l):
        l = l.split(';')[0].rstrip()
        return l
    def parse(s, text):
        items = []  # (label list, mnemonic, operands, srcline)
        pending = []
        seg = 'c'; epos = 0
        for ln, raw in enumerate(text.splitlines(), 1):
            l = s.clean(raw)
            if not l.strip(): continue
            m = re.match(r'^([A-Za-z_]\w*):', l)
            while m:
                pending.append(m.group(1)); l = l[m.end():]
                m = re.match(r'^\s*([A-Za-z_]\w*):', l)
            l = l.strip()
            if not l: continue
            parts = l.split(None, 1)
            mn = parts[0].lower(); ops = parts[1] if len(parts) > 1 else ''
            if mn == '.exit': break
            if mn == '.device': continue
            if mn == '.eseg': seg = 'e'; continue
            if mn == '.cseg': seg = 'c'; continue
            if mn == '.org':
                if seg == 'e': epos = s.val(ops)
                continue
            if mn == '.db' and seg == 'e':
                for b in ops.split(','):
                    s.eeprom[epos] = s.val(b.strip()) & 255; epos += 1
                continue
            if mn == '.equ':
                n, v = [x.strip() for x in ops.split('=', 1)]
                s.equ[n] = ('expr', v); continue
            if mn == '.def':
                n, v = [x.strip() for x in ops.split('=', 1)]
                s.defs[n] = int(v[1:]); continue
            for p in pending: s.labels[p] = len(items)
            pending = []
            items.append((mn, [o.strip() for o in ops.split(',')] if ops else [], ln))
        for p in pending: s.labels[p] = len(items)
        s.items = items
        s.cache = {}
    def val(s, expr, ln=0):
        def sub(m):
            n = m.group(0)
            if n in ('exp2','low','high'): return n
            if n in s.equ:
                v = s.equ[n]
                if v[0] == 'expr':
                    r = s.val(v[1]); s.equ[n] = ('val', r); return str(r)
                return str(v[1])
            if n in s.labels: return str(s.labels[n])
            raise ValueError('line %d: unknown symbol %s' % (ln, n))
        e = re.sub(r'\b[A-Za-z_]\w*\b', sub, expr)
        e = re.sub(r'\b0x([0-9A-Fa-f]+)\b', lambda m: str(int(m.group(1), 16)), e)
        return int(eval(e, {'exp2': lambda x: 2 ** x, 'low': lambda x: x & 255, 'high': lambda x: (x >> 8) & 255}))
    def reg(s, t, ln):
        t = t.strip()
        if t in s.defs: return s.defs[t]
        m = re.match(r'^[rR](\d+)$', t)
        if m: return int(m.group(1))
        raise ValueError('line %d: bad register %s' % (ln, t))

BRANCH = {'breq': ('Z', 1), 'brne': ('Z', 0), 'brlo': ('C', 1), 'brsh': ('C', 0), 'brcc': ('C', 0),
          'brcs': ('C', 1), 'brts': ('T', 1), 'brtc': ('T', 0), 'brmi': ('N', 1), 'brpl': ('N', 0)}

class CPU:
    def __init__(s, asm, comp=None, on_out=None, tw=0, eps_fn=None, eeprom=None):
        s.a = asm; s.r = [0] * 32
        s.eeprom = list(eeprom if eeprom is not None else asm.eeprom); s.eear = 0; s.eedr = 0; s.extra = 0
        s.f = dict(C=0, Z=0, N=0, V=0, T=0, I=0)
        s.pc = 0; s.cyc = 0; s.t = 0.0; s.stack = []
        s.tcnt = 0; s.tifr = 0; s.timsk = 0; s.tccr = 0
        s.portb = 0; s.portd = 0; s.ddrb = 0; s.ddrd = 0
        s.comp = comp; s.on_out = on_out; s.tw = tw; s.eps_fn = eps_fn
        s.idelay = 0; s.maxdepth = 0; s.ovf_cyc = []; s.wdr_cyc = []
        s.prog = [s.compile(i) for i in range(len(asm.items))]
        s.isr_entries = []
    # ---- flags
    def setnz(s, v):
        s.f['Z'] = 1 if (v & 255) == 0 else 0
        s.f['N'] = (v >> 7) & 1
    def compile(s, idx):
        a = s.a; mn, ops, ln = a.items[idx]
        R = lambda i: a.reg(ops[i], ln)
        K = lambda i: a.val(ops[i], ln) & 0xFFFF
        r = s.r; f = s.f
        def ret(n): return n
        if mn == 'nop': return lambda: 1
        if mn in ('rjmp', 'rcall'):
            tgt = a.val(ops[0], ln)
            if mn == 'rjmp':
                def x(): s.pc = tgt; return 2
            else:
                def x():
                    s.stack.append(s.pc); s.pc = tgt
                    if len(s.stack) > s.maxdepth: s.maxdepth = len(s.stack)
                    return 3
            return x
        if mn == 'ret':
            def x(): s.pc = s.stack.pop(); return 4
            return x
        if mn == 'reti':
            def x(): s.pc = s.stack.pop(); f['I'] = 1; s.idelay = 1; return 4
            return x
        if mn == 'sei':
            def x(): f['I'] = 1; s.idelay = 1; return 1
            return x
        if mn == 'cli':
            def x(): f['I'] = 0; return 1
            return x
        if mn == 'wdr':
            def x(): s.wdr_cyc.append(s.cyc); return 1
            return x
        if mn == 'set':
            def x(): f['T'] = 1; return 1
            return x
        if mn == 'clt':
            def x(): f['T'] = 0; return 1
            return x
        if mn == 'out':
            io = K(0); d = R(1)
            def x(): s.write_io(io, r[d]); return 1
            return x
        if mn == 'in':
            d = R(0); io = K(1)
            def x(): r[d] = s.read_io(io); return 1
            return x
        if mn in ('sbi', 'cbi'):
            io = K(0); b = K(1); set_ = mn == 'sbi'
            def x():
                v = s.read_io(io, raw=True)
                v = (v | (1 << b)) if set_ else (v & ~(1 << b) & 255)
                s.write_io(io, v); return 2
            return x
        if mn == 'mov':
            d = R(0); sr = R(1)
            def x(): r[d] = r[sr]; return 1
            return x
        if mn == 'ldi':
            d = R(0); k = K(1) & 255
            def x(): r[d] = k; return 1
            return x
        if mn in ('andi', 'cbr', 'ori', 'sbr'):
            d = R(0); k = K(1) & 255
            if mn in ('cbr',): k = (~k) & 255
            if mn in ('andi', 'cbr'):
                def x(): r[d] &= k; s.setnz(r[d]); f['V'] = 0; return 1
            else:
                def x(): r[d] |= k; s.setnz(r[d]); f['V'] = 0; return 1
            return x
        if mn in ('cpi', 'subi'):
            d = R(0); k = K(1) & 255; keep = mn == 'cpi'
            def x():
                v = r[d]; res = v - k
                f['C'] = 1 if res < 0 else 0
                res &= 255; s.setnz(res)
                if not keep: r[d] = res
                return 1
            return x
        if mn == 'cpc':
            d = R(0); sr = R(1)
            def x():
                res = r[d] - r[sr] - f['C']; f['C'] = 1 if res < 0 else 0
                z = 1 if (res & 255) == 0 else 0
                f['Z'] = z & f['Z']; f['N'] = (res >> 7) & 1; return 1
            return x
        if mn == 'tst':
            d = R(0)
            def x(): s.setnz(r[d]); f['V'] = 0; return 1
            return x
        if mn in ('cp',):
            d = R(0); sr = R(1)
            def x():
                res = r[d] - r[sr]; f['C'] = 1 if res < 0 else 0; s.setnz(res & 255); return 1
            return x
        if mn in ('eor', 'and', 'or'):
            d = R(0); sr = R(1)
            def x():
                if mn == 'eor': r[d] ^= r[sr]
                elif mn == 'and': r[d] &= r[sr]
                else: r[d] |= r[sr]
                s.setnz(r[d]); f['V'] = 0; return 1
            return x
        if mn == 'clr':
            d = R(0)
            def x(): r[d] = 0; f['Z'] = 1; f['N'] = 0; f['V'] = 0; return 1
            return x
        if mn == 'add':
            d = R(0); sr = R(1)
            def x():
                res = r[d] + r[sr]; f['C'] = res >> 8; r[d] = res & 255; s.setnz(r[d]); return 1
            return x
        if mn == 'neg':
            d = R(0)
            def x():
                res = (-r[d]) & 255; f['C'] = 0 if res == 0 else 1; r[d] = res; s.setnz(res); return 1
            return x
        if mn in ('dec', 'inc'):
            d = R(0); dl = -1 if mn == 'dec' else 1
            def x(): r[d] = (r[d] + dl) & 255; s.setnz(r[d]); return 1
            return x
        if mn == 'swap':
            d = R(0)
            def x(): r[d] = ((r[d] << 4) | (r[d] >> 4)) & 255; return 1
            return x
        if mn in ('lsl', 'lsr'):
            d = R(0)
            if mn == 'lsl':
                def x(): v = r[d]; f['C'] = v >> 7; r[d] = (v << 1) & 255; s.setnz(r[d]); return 1
            else:
                def x(): v = r[d]; f['C'] = v & 1; r[d] = v >> 1; s.setnz(r[d]); return 1
            return x
        if mn == 'bst':
            d = R(0); b = K(1)
            def x(): f['T'] = (r[d] >> b) & 1; return 1
            return x
        if mn == 'bld':
            d = R(0); b = K(1)
            def x():
                r[d] = (r[d] | (1 << b)) if f['T'] else (r[d] & ~(1 << b) & 255); return 1
            return x
        if mn in ('sbrc', 'sbrs'):
            d = R(0); b = K(1); want = 1 if mn == 'sbrs' else 0
            def x():
                if ((r[d] >> b) & 1) == want: s.pc += 1; return 2
                return 1
            return x
        if mn in BRANCH:
            fl, want = BRANCH[mn]; tgt = a.val(ops[0], ln)
            def x():
                if f[fl] == want: s.pc = tgt; return 2
                return 1
            return x
        raise ValueError('line %d: unsupported %s' % (ln, mn))
    # ---- IO
    def read_io(s, io, raw=False):
        if io == 0x08: return (s.comp(s) << 5) if s.comp else 0x20
        if io == 0x32: return s.tcnt
        if io == 0x1D: return s.eedr
        if io == 0x1E: return s.eear
        if io == 0x38: return s.tifr
        if io == 0x18: return s.portb
        if io == 0x12: return s.portd
        return 0
    def write_io(s, io, v):
        v &= 255
        if io == 0x12:
            s.portd = v
            if s.on_out: s.on_out('D', v, s)
        elif io == 0x18:
            s.portb = v
            if s.on_out: s.on_out('B', v, s)
        elif io == 0x1E: s.eear = v & 63
        elif io == 0x1C:
            if v & 1: s.eedr = s.eeprom[s.eear & 63]; s.extra = 4
        elif io == 0x32: s.tcnt = (v + s.tw) & 255; s.tcnt_written = True
        elif io == 0x38: s.tifr &= ~v
        elif io == 0x39: s.timsk = v
        elif io == 0x33: s.tccr = v
        elif io == 0x11: s.ddrd = v
        elif io == 0x17: s.ddrb = v
    # ---- run
    def run(s, max_cycles, stop=None):
        prog = s.prog; f = s.f
        while s.cyc < max_cycles:
            if s.pc >= len(prog): raise RuntimeError('pc out of range %d' % s.pc)
            fn = prog[s.pc]; s.pc += 1
            s.tcnt_written = False
            c0 = s.cyc
            n = fn()
            n += s.extra; s.extra = 0
            s.cyc += n
            if s.eps_fn: s.t += n * 100.0 * (1 + s.eps_fn(s))
            else: s.t += n * 100.0
            if s.tccr & 7 == 1:
                if s.tcnt_written: s.tcnt = s.tcnt  # write wins this cycle
                else:
                    s.tcnt += n
                    if s.tcnt >= 256:
                        s.tcnt -= 256; s.tifr |= 2; s.ovf_cyc.append(s.cyc)
            if s.idelay: s.idelay = 0
            elif f['I'] and (s.timsk & 2) and (s.tifr & 2):
                s.tifr &= ~2; s.stack.append(s.pc); f['I'] = 0; s.pc = 2
                if len(s.stack) > s.maxdepth: s.maxdepth = len(s.stack)
                s.cyc += 4; s.t += 400.0 * (1 + (s.eps_fn(s) if s.eps_fn else 0))
                if s.tccr & 7 == 1:
                    s.tcnt += 4
                    if s.tcnt >= 256: s.tcnt -= 256; s.tifr |= 2
                s.isr_entries.append(s.cyc)
            if stop and stop(s): break
