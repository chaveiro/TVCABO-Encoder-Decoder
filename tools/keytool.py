#!/usr/bin/env python3
"""keytool - create / edit / inspect the shared key of the TVRabo PAL scrambler.

The key is KEYLEN (=4) bytes stored in the AT90S1200 EEPROM, addresses 0..3.
An encoder and a decoder only decode each other when their keys are equal.
Erased EEPROM (FF FF FF FF) = STANDARD mode = no key = original behaviour.

    keytool.py gen [NAME]            random key       -> keys/NAME.{key,inc,eep.hex}
    keytool.py set HEX [NAME]        key typed by you (8 hex digits, e.g. 1A2B3C4D)
    keytool.py passphrase TEXT [NAME]  key derived from a passphrase (SHA-256)
    keytool.py standard [NAME]       the standard (no key) image
    keytool.py show FILE             read a .key/.inc/.eep.hex file and print it
    keytool.py table HEX             print F(n) for n = 0..255 (to check firmware)
    keytool.py install NAME          copy keys/NAME.inc to firmware/key.inc

Python 3 standard library only.  Key files in keys/ are git-ignored: never
publish a real key.
"""
import hashlib, os, re, secrets, shutil, sys

KEYLEN = 4                      # must match .equ KEYLEN in the firmware (even)
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
KEYS = os.path.join(ROOT, 'keys')


def F(n, key):
    """Exactly what keymix does: for i = KEYLEN-1..0: t=k[i]+1; x=swap(x+t)^t."""
    x = n & 255
    for i in reversed(range(KEYLEN)):
        t = (key[i] + 1) & 255
        x = (x + t) & 255
        x = ((x << 4) | (x >> 4)) & 255
        x ^= t
    return x


def encoder_mask(nonce, key):
    """Mask the ENCODER builds for a data line with nonce byte `nonce`:
    the decoder holds desco = 0xE0|(nonce>>3) (it samples 3 bit-times early),
    computes M = F(desco); the encoder sends V,B = pattern ^ rol3(M)."""
    m = F(0xE0 | (nonce >> 3), key)
    return ((m << 3) | (m >> 5)) & 255


def parse_hex(s):
    s = re.sub(r'[^0-9A-Fa-f]', '', s)
    if len(s) != 2 * KEYLEN:
        sys.exit('key must be exactly %d hex digits (%d bytes), got %d digits' % (2 * KEYLEN, KEYLEN, len(s)))
    return list(bytes.fromhex(s))


def ihex(data):
    """Intel HEX image of the EEPROM (address 0)."""
    out = []
    rec = [len(data), 0, 0, 0] + list(data)
    out.append(':' + ''.join('%02X' % b for b in rec) + '%02X' % ((-sum(rec)) & 255))
    out.append(':00000001FF')
    return '\n'.join(out) + '\n'


def write_all(name, key):
    os.makedirs(KEYS, exist_ok=True)
    h = ''.join('%02X' % b for b in key)
    std = all(b == 0xFF for b in key)
    with open(os.path.join(KEYS, name + '.key'), 'w') as f:
        f.write(h + '\n')
    with open(os.path.join(KEYS, name + '.inc'), 'w') as f:
        f.write('; key.inc - EEPROM image of the shared key (%d bytes)%s\n' % (KEYLEN, ' - STANDARD MODE (no key)' if std else ''))
        f.write('\t.eseg\n\t.org\t0\n\t.db\t' + ','.join('0x%02X' % b for b in key) + '\n\t.cseg\n')
    with open(os.path.join(KEYS, name + '.eep.hex'), 'w') as f:
        f.write(ihex(key))
    print('key        : %s%s' % (h, '   (STANDARD: no key)' if std else ''))
    print('written    : keys/%s.key  keys/%s.inc  keys/%s.eep.hex' % (name, name, name))
    print('program    : avrdude -p 1200 -c <your-programmer> -U eeprom:w:keys/%s.eep.hex:i' % name)
    print('F(0..3)    : ' + ' '.join('%02X' % F(n, key) for n in range(4)) + '   (self-test vector)')


def check_key(key):
    if all(b == 0xFF for b in key):
        print('note: FF FF FF FF is the erased state = standard mode (that is what you asked for).')


def load_any(path):
    t = open(path).read()
    if path.endswith('.hex'):
        line = t.splitlines()[0].strip()
        n = int(line[1:3], 16)
        return list(bytes.fromhex(line[9:9 + 2 * n]))[:KEYLEN]
    if '.db' in t:
        m = re.search(r'\.db\s+([^\n;]+)', t)
        return [int(x.strip(), 0) for x in m.group(1).split(',')][:KEYLEN]
    return parse_hex(t)


def main(a):
    if len(a) < 2 or a[1] in ('-h', '--help', 'help'):
        print(__doc__); return
    c = a[1]
    if c == 'gen':
        while True:
            key = list(secrets.token_bytes(KEYLEN))
            if not all(b == 0xFF for b in key): break
        write_all(a[2] if len(a) > 2 else 'mykey', key)
    elif c == 'set' and len(a) >= 3:
        key = parse_hex(a[2]); check_key(key)
        write_all(a[3] if len(a) > 3 else 'mykey', key)
    elif c == 'passphrase' and len(a) >= 3:
        key = list(hashlib.sha256(a[2].encode('utf-8')).digest()[:KEYLEN])
        if all(b == 0xFF for b in key): sys.exit('unlucky passphrase (hashes to the standard key); change it')
        write_all(a[3] if len(a) > 3 else 'mykey', key)
    elif c == 'standard':
        write_all(a[2] if len(a) > 2 else 'standard', [0xFF] * KEYLEN)
    elif c == 'show' and len(a) >= 3:
        key = load_any(a[2]); print('key :', ''.join('%02X' % b for b in key)); check_key(key)
    elif c == 'table' and len(a) >= 3:
        key = parse_hex(a[2])
        for r in range(16):
            print(' '.join('%02X' % F(r * 16 + k, key) for k in range(16)))
    elif c == 'install' and len(a) >= 3:
        src = os.path.join(KEYS, a[2] + '.inc')
        if not os.path.exists(src): sys.exit('no such key: ' + src)
        shutil.copy(src, os.path.join(ROOT, 'firmware', 'key.inc'))
        print('copied to firmware/key.inc  (do NOT commit it; see USAGE.md)')
    else:
        print(__doc__); sys.exit(1)


if __name__ == '__main__':
    main(sys.argv)
