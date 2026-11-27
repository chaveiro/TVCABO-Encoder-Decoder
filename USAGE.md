# USAGE

## 1. What you need
* The V41 board (schematic: `hardware/schematic_v41.jpg`): AT90S1200 @ 10 MHz, 4051 mux, VCXO trimmer C1.
* An AVR assembler (AVRASM2 / avra – see the *Status* note in README) and an ISP programmer able to
  write **flash and EEPROM** of an AT90S1200 (`avrdude -p 1200`).
* Python 3 (+ numpy for the emulator tests).

## 2. Roles: one board = one firmware
| Board | Flash | Input | Output |
|---|---|---|---|
| **Decoder** | `firmware/decoder.asm` | coded PAL on the SCART input | normal PAL |
| **Encoder** | `firmware/encoder.asm` | clean PAL (625 lines) on the SCART input | coded PAL |

Both use the same hardware. The encoder drives the 4051 select lines PD3..PD5 exactly like the
decoder and relies on the same comparator input (sync) and VCXO circuit.

## 3. Standard mode (no key) – default
1. Assemble `decoder.asm` / `encoder.asm`, program the flash.
2. Leave the EEPROM **erased** (`FF`). A new/blank AT90S1200 already is.
3. Done: this encoder works with the *original, unmodified* decoder firmware, and the
   patched decoder works with any original-compatible coded signal.

`firmware/key.inc` ships as `FF FF FF FF`; assembling with it generates no non-default EEPROM.

## 4. Shared key – create, edit, install
The key is **4 bytes** (8 hex digits) in EEPROM addresses 0..3. Encoder and decoder must hold
the **same** key. `FF FF FF FF` means "no key".

### Create
```
python3 tools/keytool.py gen mykey                 # random key
python3 tools/keytool.py passphrase "our secret" mykey   # derived from a passphrase (SHA-256)
python3 tools/keytool.py set 1A2B3C4D mykey        # you choose the 8 hex digits
```
Each command writes, in `keys/` (git-ignored):
`mykey.key` (hex text), `mykey.inc` (assembler EEPROM image), `mykey.eep.hex` (Intel HEX),
and prints the self-test vector `F(0..3)`.

### Edit / change a key
Run the command again with new digits (`set`) or a new name. To inspect:
```
python3 tools/keytool.py show keys/mykey.eep.hex     # also reads .key and .inc
python3 tools/keytool.py table 1A2B3C4D               # full F table (to compare with firmware)
```
To change the key on a board: write a new EEPROM image – **no re-assembling needed** (flash is the
same for every key):
```
avrdude -p 1200 -c <programmer> -P <port> -U eeprom:w:keys/mykey.eep.hex:i
```
(the AT90S1200 has no bootloader; use ISP. Verify with `-U eeprom:r:-:i`.)

### Back to standard mode
```
python3 tools/keytool.py standard
avrdude -p 1200 -c <programmer> -U eeprom:w:keys/standard.eep.hex:i     # or just erase the chip
```

### Alternative: bake the key into the build
`python3 tools/keytool.py install mykey` copies `keys/mykey.inc` to `firmware/key.inc`; your assembler
then emits a `.eep` file next to the `.hex`. **Do not commit a real `key.inc`** – run
`git update-index --skip-worktree firmware/key.inc` first, or restore the default before committing.

### Rules
* Same key on both boards, 4 bytes. Anything else behaves like a different key.
* `FF FF FF FF` is standard mode, not a key. Keys with some `FF` bytes are fine.
* Wrong key / mixed standard+keyed: the decoder still *locks* (sync is key-independent) but
  mis-reads the inversion flags, so the picture is wrongly (un)inverted, mostly scrambled and
  flickering. In emulation 11–52 % of the data lines still gave the right flags by chance (1-bit-different key: 11 %; missing key on one side: ~50 %); it is not a lock-out.
* Keep keys out of git (`keys/` is ignored). Treat the key as a pairing code, not a secret
  (`docs/PROTOCOL.md` §6).

## 5. Build
```
python3 tools/gen_encoder.py      # only needed if you edit firmware/encoder.tpl
avrasm2 -fI -I firmware firmware/decoder.asm -o decoder.hex -e decoder.eep
avrasm2 -fI -I firmware firmware/encoder.asm -o encoder.hex -e encoder.eep
avrdude -p 1200 -c <prog> -U flash:w:decoder.hex:i      # decoder board
```
Fuses: the AT90S1200 has none for the clock – use the 10 MHz crystal XT1. The firmware
enables the watchdog itself. Adjust trimmer **C1** so the VCXO sits near its centre (the decoder
only acquires if the sync edge falls inside its capture window).

## 6. Connections / signals (from the firmware)
* PB0/PB1 (AIN0/AIN1): comparator (sync slicer). ACSR bit 5 = 0 means sync present.
* PB3: VCXO dither, PB7: VCXO enable, PB4: clamp, PB2: "data window" marker (high while the decoder
  samples the data bits – handy to scope), PB6: output switch.
* PD3..PD5: 4051 A/B/C select = output code `vn=00h, vi=20h, bn=00h, bi=10h, pr=08h(black), sy=28h(sync)`.
Check them against your copy of the schematic.

## 7. Bring-up and calibration of the encoder (do this with a scope / logic analyser)
1. Feed the encoder clean PAL; check regenerated sync (4.6 µs) every 64 µs on the output.
2. Feed the encoder output to a **standard-mode** decoder board. Watch decoder PB2 (data marker): it
   must pulse on lines 5 and 317. If it never does, the reference pulses (lines 335/336, 622/623) are
   not seen: check the comparator threshold (`TH` in the emulator = sync threshold).
3. Bit alignment: the data bits are emitted aligned to the decoder's sampling instants so that
   the decoder's first register reads `111` + the top 5 bits of the nonce. If your analog path adds
   delay, shift `PAD0` (default 11; `python3 tools/gen_encoder.py <pad0>`, 1 cycle = 0.1 µs) and regenerate. In emulation the sample instants sit 0.30 µs (min) from the nearest bit edge at 11, but only 0.10–0.20 µs at 9 or 13, so a delay of 2 cycles matters; the flags
   are robust to errors in the non-key bits but not to a whole-bit shift in keyed mode.
4. Only then program keys.

## 8. Tests (emulator, no hardware)
```
python3 tests/run_tests.py quick     # ~1 min: size, key functions, std->std, keyed->keyed, std==original
python3 tests/run_tests.py           # + mismatched-key scenarios (several minutes)
```
