import numpy as np
RES = 50.0            # ns per sample
LINE = 64000.0
FRAME = 625 * LINE
SYNC, BLACK, WHITE = 0.0, 0.3, 1.0

def clean_pal(nframes=1, active=True, extra_pulses=None):
    """Return level array (period = 1 frame) for clean 625-line PAL. extra_pulses: list of (h, start_us, width_us) sync-level pulses added at half-line h."""
    n = int(FRAME / RES)
    x = np.full(n, BLACK, dtype=np.float32)
    def U(us): return int(round(us * 1000 / RES))
    # video ramp
    if active:
        for line in range(1, 626):
            if (24 <= line <= 310) or (337 <= line <= 623):
                s = (line - 1) * U(64) + U(12.0); e = (line - 1) * U(64) + U(62.0)
                x[s:e] = np.linspace(BLACK, WHITE, e - s)
    pulses = {}
    eq = set(); br = set()
    for base in (0, 625):
        for k in range(5):
            br.add(base + k); eq.add(base + 5 + k); eq.add((base - 5 + k) % 1250)
    for h in range(1250):
        if h in br: pulses[h] = 27.3
        elif h in eq: pulses[h] = 2.35
        elif h % 2 == 0: pulses[h] = 4.7
    for h, w in pulses.items():
        # VBI: even-h regular syncs replaced by eq/broad (already in dict); clear video in that line start region
        s = h * U(32); x[s:s + U(w)] = SYNC
    if extra_pulses:
        for h, st, w in extra_pulses:
            s = h * U(32) + U(st); x[s:s + U(w)] = SYNC
    return x
