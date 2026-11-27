#!/usr/bin/env python3
"""Generate docs/img/*.png from a closed-loop EMULATION run (encoder -> coded PAL -> decoder).
Usage: python3 tools/make_figures.py        (needs numpy + matplotlib; ~20 s)
"""
import os, sys, bisect, pickle
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'sim')); sys.path.insert(0, HERE)
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from harness import load, closed_loop, build_wave, FW, RES, FRAME
import keytool

OUT = os.path.join(HERE, '..', 'docs', 'img')
KEY = [0x1A, 0x2B, 0x3C, 0x4D]
CACHE = '/tmp/tvrabo_fig_data.pkl'
COL = {0x00: '#2a9d8f', 0x20: '#e76f51', 0x08: '#adb5bd', 0x28: '#212529', 0x10: '#8e5ad7'}
# note: vn and bn share code 0x00, so one colour; bi=0x10, vi=0x20
NAME = {0x00: 'vn/bn', 0x20: 'vi', 0x10: 'bi', 0x08: 'pr', 0x28: 'sy'}

def capture():
    enc = load(FW + '/encoder.asm', KEY); dec = load(FW + '/decoder.asm', KEY)
    EL = []; DL = []; SM = []; DR = []
    def e_t(c): EL.append((c.t, c.r[24] * 256 + c.r[23], (c.r[20] >> 2) & 1, c.r[20] & 3))
    def e_d(c): DL.append((c.t, c.r[24] * 256 + c.r[23], c.r[17], c.r[18], c.r[19], c.r[20] & 3, c.r[5]))
    def d_s(c): SM.append(c.t + 100.0)
    def d_k(c): DR.append((c.t, c.r[17], c.r[18], c.r[19]))
    R = closed_loop(enc, dec, nfr=24, ehooks={'tmrov': e_t, 'dline': e_d},
                    dhooks={'c1': d_s, 'c3': d_s, 'c5': d_s, 'c7': d_s, 'c9': d_s, 'c11': d_s, 'keymix': d_k})
    tmax = R['ecpu'].t - 1000
    dec_wave = build_wave(R['dev'], R['wave'], tmax - 2e6, R['offs_d'])
    return dict(ev=R['ev'], dev=R['dev'], wave=R['wave'], dwave=dec_wave, sig=R['sig'], offs_e=R['offs_e'],
                offs_d=R['offs_d'], EL=EL, DL=DL, SM=SM, DR=DR)

def get():
    if os.path.exists(CACHE): return pickle.load(open(CACHE, 'rb'))
    D = capture(); pickle.dump(D, open(CACHE, 'wb')); return D

class Ctx:
    def __init__(s, D):
        s.D = D
        s.evt = [e[0] for e in D['ev']]; s.evc = [e[1] for e in D['ev']]
        s.dvt = [e[0] for e in D['dev']]; s.dvc = [e[1] for e in D['dev']]
        s.ls = [e for e in D['EL'] if e[2] == 0]            # line-start sections
        s.lst = [e[0] for e in s.ls]
    def line(s, n, after):
        """line-start record for line number n, first one after time `after`."""
        for e in s.ls:
            if e[0] > after and e[1] == n: return e
    def code_enc(s, t):
        i = bisect.bisect_right(s.evt, t) - 1; return s.evc[i] if i >= 0 else 0x08
    def code_dec(s, tc):          # tc in coded-time axis
        t = tc - s.D['offs_d']; i = bisect.bisect_right(s.dvt, t) - 1; return s.dvc[i] if i >= 0 else 0x08
    def seg_enc(s, a, b):
        i = bisect.bisect_right(s.evt, a) - 1; out = []
        t = a; c = s.evc[max(i, 0)]
        for j in range(max(i, 0) + 1, len(s.evt)):
            if s.evt[j] >= b: break
            out.append((t, s.evt[j], c)); t = s.evt[j]; c = s.evc[j]
        out.append((t, b, c)); return out
    def seg_dec(s, a, b):
        o = s.D['offs_d']; r = []
        for (x, y, c) in s.seg_dec_raw(a - o, b - o): r.append((x + o, y + o, c))
        return r
    def seg_dec_raw(s, a, b):
        i = bisect.bisect_right(s.dvt, a) - 1; out = []; t = a; c = s.dvc[max(i, 0)]
        for j in range(max(i, 0) + 1, len(s.dvt)):
            if s.dvt[j] >= b: break
            out.append((t, s.dvt[j], c)); t = s.dvt[j]; c = s.dvc[j]
        out.append((t, b, c)); return out
    def wav(s, key, a, b, shift=0.0):
        arr = s.D[key]; i0 = int((a + shift) / RES); i1 = int((b + shift) / RES)
        y = arr[i0:i1]; x = (np.arange(len(y)) * RES + (a + shift) - shift) ; return (x - a) / 1000.0, y
    def sig_in(s, a, b):
        sig = s.D['sig']; N = len(sig); idx = ((np.arange(int(a / RES), int(b / RES)) * RES + s.D['offs_e']) / RES).astype(int) % N
        return (np.arange(len(idx)) * RES) / 1000.0, sig[idx]

def strip(ax, segs, t0, y0=0, h=1, label=True):
    for (a, b, c) in segs:
        ax.add_patch(Rectangle(((a - t0) / 1000.0, y0), (b - a) / 1000.0, h, color=COL.get(c, '#ccc'), lw=0))
        if label and (b - a) > 2500: ax.text(((a + b) / 2 - t0) / 1000.0, y0 + h / 2, NAME.get(c, hex(c)), ha='center', va='center', fontsize=6.5, color='white')

def fig_lines(C, fig):
    D = C.D; t_start = 18 * FRAME / 1.0 * 0 + 17e8 * 0 + 5e8
    cols = []
    def pick(n, flags, after=5e8):
        for e in C.ls:
            if e[0] > after and e[1] == n and (flags is None or e[3] == flags) and e[0] < 9.2e8: return e
    cols = [('line 100 – flags V=1 B=1\n(video + burst inverted)', pick(100, 3)),
            ('line 100 – flags V=0 B=0\n(normal)', pick(100, 0)),
            ('line 335 – reference pulse\n(pair A; B = lines 622/623)', pick(335, None)),
            ('line 5 – data line\n(24 bits)', pick(5, 3) or pick(5, 0) or pick(5, 1) or pick(5, 2))]
    gs = fig.add_gridspec(6, 4, height_ratios=[3, 3, 0.55, 3, 0.55, 0.05], hspace=0.12, wspace=0.12, left=0.075, right=0.995, top=0.88, bottom=0.07)
    rows = ['clean PAL\ninput', 'CODED output\n(encoder)', 'mux code\n(encoder)', 'DECODED output\n(decoder)', 'mux code\n(decoder)']
    for j, (title, e) in enumerate(cols):
        t0 = e[0] + 4700.0 - 4700.0 + 0.0           # tmrov instant
        edge = e[0] + 4700.0                         # sync leading edge (first 'sy' of the line)
        a = edge - 3000.0; b = edge + 61000.0
        axs = [fig.add_subplot(gs[i, j]) for i in range(5)]
        x, y = C.sig_in(a, b); axs[0].plot(x - 3.0, y, color='#495057', lw=1)
        x, y = C.wav('wave', a, b); axs[1].plot(x - 3.0, y, color='#c1121f', lw=1)
        x, y = C.wav('dwave', a - D['offs_d'], b - D['offs_d']); axs[3].plot(x - 3.0, y, color='#0b7285', lw=1)
        strip(axs[2], C.seg_enc(a, b), edge); strip(axs[4], C.seg_dec(a, b), edge)
        for i, ax in enumerate(axs):
            ax.set_xlim(-3, 61)
            if i in (0, 1, 3): ax.set_ylim(-0.1, 1.45); ax.set_yticks([0, 0.3, 1.0]); ax.grid(alpha=.25)
            else: ax.set_ylim(0, 1); ax.set_yticks([])
            if i < 4: ax.set_xticklabels([])
            if j: ax.set_yticklabels([]) if i in (0, 1, 3) else None
            if j == 0: ax.set_ylabel(rows[i], fontsize=8)
            ax.tick_params(labelsize=7)
            for v in (0, 4.7): ax.axvline(v, color='#999', lw=.4, ls=':')
        axs[0].set_title(title, fontsize=8.5)
        axs[4].set_xlabel('µs after the line-sync leading edge', fontsize=7.5)
    fig.suptitle('B. Four kinds of line, in the clean input, the coded signal and the decoded signal   (levels: sync 0, black 0.3, white 1.0)', fontsize=10, x=0.5, y=0.985)
    return cols

def fig_frame(C, fig):
    D = C.D
    # pick a frame whose line-5 data line has flags 2 and line-317 flags 3 (or any consecutive pair) after lock
    cand = [(i, d) for i, d in enumerate(D['DL']) if d[1] == 5 and d[0] > 5e8 and i + 1 < len(D['DL'])]
    i, d5 = next(((i, d) for i, d in cand if d[5] == 2), cand[0]); d317 = D['DL'][i + 1]
    start = None
    for e in C.ls:
        if e[1] == 1 and e[0] < d5[0] and e[0] > d5[0] - 5 * 64000 * 1.1 and False: start = e
    # lines 1..625 of the frame that contains d5
    L = {}
    for e in C.ls:
        if d5[0] - 6 * 64000 < e[0] < d5[0] + 625 * 64000 - 5 * 64000: L.setdefault(e[1], e)
    lines = list(range(1, 626))
    t_of = lambda n: L[n][0] + (0 if n >= 5 else 625 * 64000) if False else L[n][0]
    def cls(code_fn, n, t0):
        edge = t0 + 4700.0
        v = code_fn(edge + 40000.0); bcode = code_fn(edge + 7000.0); ref = code_fn(edge + 33000.0)
        # data / reference detection from number of transitions in 13..36us
        return v, bcode, ref
    ax = [fig.add_subplot(3, 1, k + 1) for k in range(3)]
    lab = ['clean input', 'CODED (encoder output)', 'DECODED (decoder output)']
    first = None
    for n in lines:
        if n not in L: continue
        t0 = L[n][0]; edge = t0 + 4700.0
        for k in range(3):
            if k == 0:
                inv = 24 <= n <= 308 or 337 <= n <= 621
                v = 0x00 if inv else 0x08; b = 0x08; ref = None; dat = False
                ax[k].add_patch(Rectangle((n - .5, 0.55), 1, 0.4, color=COL[v], lw=0))
                continue
            code = (C.code_enc if k == 1 else C.code_dec)
            cf = code if k == 1 else (lambda t, code=code: C.code_dec(t))
            v = cf(edge + 40000.0); b = cf(edge + 7000.0)
            ax[k].add_patch(Rectangle((n - .5, 0.55), 1, 0.4, color=COL.get(v, '#ccc'), lw=0))
            ax[k].add_patch(Rectangle((n - .5, 0.1), 1, 0.35, color=COL.get(b, '#ccc'), lw=0))
            # reference pulse / data line: sync level 25us after the edge
            if n in (5, 317): ax[k].plot([n], [1.12], marker='v', color='#6a040f', ms=5)
            if n in (335, 336, 622, 623): ax[k].plot([n], [1.12], marker='D', color='#003049', ms=4)
    for k in range(3):
        ax[k].set_xlim(0, 626); ax[k].set_ylim(0, 1.3); ax[k].set_yticks([0.27, 0.75]); ax[k].set_yticklabels(['burst\nwindow', 'video\nwindow'], fontsize=7)
        ax[k].set_title(lab[k], loc='left', fontsize=8.5, pad=2); ax[k].tick_params(labelsize=7)
        if k < 2: ax[k].set_xticklabels([])
        for v in (313,): ax[k].axvline(v, color='#999', lw=.5, ls=':')
    ax[2].set_xlabel('line number (625-line frame; field 1 = lines 1–312, field 2 = 313–625)', fontsize=8)
    ax[1].text(8, 1.17, 'data line 5', fontsize=6.5, ha='left', color='#6a040f'); ax[1].text(284, 1.17, 'data line 317', fontsize=6.5, ha='right', color='#6a040f')
    ax[1].text(340, 1.17, 'ref. pair A 335/336', fontsize=6.5, color='#003049'); ax[1].text(618, 1.17, 'pair B 622/623', fontsize=6.5, ha='right', color='#003049')
    fl = lambda f: 'V=%d B=%d' % (f & 1, (f >> 1) & 1)
    ax[1].text(120, 1.17, 'field 1 flags (line 5): ' + fl(d5[5]), fontsize=7, color='#333')
    ax[1].text(450, 1.17, 'field 2 flags (line 317): ' + fl(d317[5]), fontsize=7, color='#333')
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(color=COL[0x00], label='vn / bn  0x00  (normal)'), Patch(color=COL[0x20], label='vi  0x20  (video inverted)'), Patch(color=COL[0x10], label='bi  0x10  (burst inverted)'), Patch(color=COL[0x08], label='pr  0x08  (black)'), Patch(color=COL[0x28], label='sy  0x28  (sync level)')], loc='lower center', ncol=5, fontsize=7.5, frameon=False)
    ax[0].text(626, 0.2, 'no burst modelled in the test input', fontsize=6.5, ha='right', color='#666')
    fig.suptitle('A. One frame (emulation): which lines are inverted in the coded signal and restored by the decoder', fontsize=10)
    fig.tight_layout(rect=(0, 0.05, 1, 0.96))

def margins(C):
    D = C.D; ev = D['ev']; evt = np.array([e[0] for e in ev]); evc = np.array([e[1] for e in ev])
    chg = [evt[i] for i in range(1, len(ev)) if evc[i] != evc[i - 1] and evc[i] in (0x08, 0x28) and evc[i - 1] in (0x08, 0x28)]
    chg = np.array(chg); out = []
    for d in D['DL']:
        e0 = d[0]; lo, hi = e0 - 6000, e0 + 20000
        tr = chg[(chg > lo) & (chg < hi)]
        sm = [s + D['offs_d'] for s in D['SM'] if lo - 5000 < s + D['offs_d'] < hi + 5000]
        for s in sm:
            if len(tr): out.append(np.min(np.abs(tr - s)))
    return (min(out) / 1000.0, float(np.median(out)) / 1000.0, len(out)) if out else (None, None, 0)

def fig_data(C, fig):
    D = C.D
    cand = [d for d in D['DL'] if d[1] == 5 and d[0] > 6e8 and d[5] in (3, 1)]
    d5 = cand[0]
    e = C.line(5, d5[0] - 64000 * 1.5)
    edge = e[0] + 4700.0; a = edge - 2000.0; b = edge + 40000.0
    K, V, B = d5[2], d5[3], d5[4]; flags = d5[5]
    bits = [(K >> (7 - i)) & 1 for i in range(8)] + [(V >> (7 - i)) & 1 for i in range(8)] + [(B >> (7 - i)) & 1 for i in range(8)]
    gs = fig.add_gridspec(4, 1, height_ratios=[3.0, 0.6, 1.8, 2.2], hspace=0.5, left=0.06, right=0.99, top=0.92, bottom=0.03)
    ax = fig.add_subplot(gs[0]); axm = fig.add_subplot(gs[1], sharex=ax)
    x, y = C.wav('wave', a, b); ax.plot(x - 2.0, y, color='#c1121f', lw=1.1)
    strip(axm, C.seg_enc(a, b), edge, label=False)
    ax.set_ylim(-0.12, 0.5); ax.set_yticks([0, 0.3]); ax.set_yticklabels(['sy (bit 0)', 'pr (bit 1)'], fontsize=7); ax.grid(alpha=.25)
    axm.set_yticks([]); axm.set_xlim(-2, 40); axm.set_xlabel('µs after the line-sync leading edge (coded line 5)', fontsize=8)
    ax.set_title('C. Data line (line 5): 24 bits, bit 1 = black level (pr 0x08), bit 0 = sync level (sy 0x28)', fontsize=10, loc='left')
    # transmitted bit cells: find emission instants from mux events (first change after 15us)
    ev = [(t, c) for t, c, _ in D['ev'] if a <= t < b]
    # sample instants of the decoder (emulated), converted to coded-time axis
    sm = [t + D['offs_d'] for t in D['SM'] if a - 0 <= t + D['offs_d'] <= b]
    for t in sm: ax.axvline((t - a) / 1000.0 - 2.0, color='#0b7285', lw=.8, ls='--')
    mn, md, nn = margins(C)
    ax.text(-1.8, 0.46, 'dashed = the 24 decoder sample instants (emulator).  Distance sample→nearest bit edge over %d samples: min %.2f µs, median %.2f µs' % (nn, mn, md), fontsize=7, color='#0b7285')
    # draw the transmitted bits as text above the first 24 encoder transitions
    em = [t for t, c in ev if 17000 + e[0] - e[0] <= (t - edge) + 4700 and True]
    # bits are emitted at q(k): take the mux events between 17 and 36us of the line-start tmrov
    bt = [t for t, c, _ in D['ev'] if e[0] + 16500 <= t <= e[0] + 36500]
    bt_all = sorted(set([e[0] + 17400.0] + bt))
    # bit cells per generator: 7.75 cycles average; use nominal t_k + shift measured from first sample
    nominal = [131 + 8 * (k % 4) + 31 * (k // 4) for k in range(24)]
    # the decoder sample k reads (stream bit k-3): place stream bit i centred on sample i+3
    for i, bit in enumerate(bits):
        if i + 3 < len(sm):
            xt = (sm[i + 3] - a) / 1000.0 - 2.0
            ax.text(xt, 0.36 if bit else 0.045, str(bit), ha='center', va='center', fontsize=7.5, color='#c1121f' if bit else '#212529', weight='bold')
    # register-mapping table
    desco = 0xE0 | (K >> 3); M = keytool.F(desco, KEY)
    vdec = ((K & 7) << 5) | (V >> 3); bdec = ((V & 7) << 5) | (B >> 3)
    xv = vdec ^ M; xb = bdec ^ M
    pc = lambda x: bin(x).count('1')
    axt = fig.add_subplot(gs[2]); axt.axis('off')
    tbl = [['sent byte', 'K = nonce', 'V (video info)', 'B (burst info)'],
           ['bits as sent', f'{K:08b}', f'{V:08b}', f'{B:08b}'],
           ['decoder register', f'desco = 111·{K>>3:05b} = {desco:02X}', f'video = {K&7:03b}·{V>>3:05b} = {vdec:02X}', f'burst = {V&7:03b}·{B>>3:05b} = {bdec:02X}'],
           ['after keymix', f'M = F(desco) = {M:02X}  (key {"".join("%02X"%k for k in KEY)})', f'video^M = {xv:02X}  → {pc(xv)} ones', f'burst^M = {xb:02X}  → {pc(xb)} ones'],
           ['decision (≥5 ones = normal)', f'flags V={flags&1} B={(flags>>1)&1}', 'inverted' if pc(xv) <= 4 else 'normal', 'inverted' if pc(xb) <= 4 else 'normal']]
    t = axt.table(cellText=tbl, loc='center', cellLoc='left', colWidths=[0.17, 0.30, 0.27, 0.26]); t.auto_set_font_size(False); t.set_fontsize(7.5); t.scale(1, 1.25)
    for (r, c), cell in t.get_celld().items():
        cell.set_linewidth(.3)
        if r == 0: cell.set_facecolor('#e9ecef')
    axn = fig.add_subplot(gs[3]); axn.axis('off')
    txt = ("How to read it\n"
           "• The decoder's three 8-sample registers start 3 bit-times BEFORE the first transmitted bit, so desco = 111 + top 5 bits of K, "
           "video = low 3 bits of K + top 5 of V, burst = low 3 of V + top 5 of B.\n"
           "• Standard mode: M = desco (key erased = identity).  Keyed mode: M = F(desco), 4 key bytes from EEPROM.\n"
           "• Encoder sends V = B = pattern ^ rol3(M); pattern 0xFF → normal, 0x00 → inverted. The five low bits of video^M / burst^M then equal the pattern,\n"
           "  the three high bits are nonce bits (0–3 ones) → 5…8 ones = normal, 0…3 ones = inverted (robust against the free bits).\n"
           "• Flags → mux codes for the field that follows:  V=1: video window uses vi (0x20) else vn (0x00);  B=1: burst window uses bi (0x10) else bn (0x00).\n"
           "• 4051 select codes on PD3..PD5:  vn/bn = 0x00 · bi = 0x10 · vi = 0x20 · pr (black) = 0x08 · sy (sync) = 0x28.")
    axn.text(0, 1, txt, va='top', fontsize=7.6, linespacing=1.45)
    return d5

def main():
    os.makedirs(OUT, exist_ok=True)
    C = Ctx(get())
    f = plt.figure(figsize=(13, 4.6)); fig_frame(C, f); f.savefig(os.path.join(OUT, 'fig_a_frame.png'), dpi=150); plt.close(f)
    f = plt.figure(figsize=(13, 7.2)); fig_lines(C, f); f.savefig(os.path.join(OUT, 'fig_b_lines.png'), dpi=150); plt.close(f)
    f = plt.figure(figsize=(13, 7.2)); fig_data(C, f); f.savefig(os.path.join(OUT, 'fig_c_data_line.png'), dpi=150); plt.close(f)
    from PIL import Image
    ims = [Image.open(os.path.join(OUT, n)).convert('RGB') for n in ('fig_a_frame.png', 'fig_b_lines.png', 'fig_c_data_line.png')]
    W = max(i.width for i in ims); H = sum(i.height for i in ims)
    comp = Image.new('RGB', (W, H), 'white'); y = 0
    for i in ims: comp.paste(i, (0, y)); y += i.height
    comp.save(os.path.join(OUT, 'protocol_signals.png'), optimize=True)
    print('written to', OUT, '(composite: protocol_signals.png %dx%d)' % (W, H))
    print('margins (min, median, n):', margins(C))

if __name__ == '__main__':
    main()
