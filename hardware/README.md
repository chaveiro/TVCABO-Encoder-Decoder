# Hardware – V41 / TVRabo box

`schematic_v41.jpg` – original schematic (dated 19-03-2003, title "V41"). Visible blocks:

* X1 / X2: SCART connectors (in / out). 7805 and 7809 regulators from J1.
* IC3 AT90S1200P with 10 MHz crystal XT1 and trimmer C1 (3–33 pF): the VCXO clock; the firmware pulls the
  crystal with PB3 (dither) and PB7 (enable) to lock to the line sync.
* Q1–Q4 etc.: input video buffer / sync separation to the comparator inputs (PB0/PB1); Q8, Q9 (BS170) near PB2/PB6.
* IC2 4051: analog mux selecting normal / inverted video, burst normal / inverted, black, sync (PD3..PD5);
  IC1A–D 4066 switches with L1–L4 (150 µH) in the video/burst paths; Q5–Q7 output stage to the SCART.

Pin usage inferred from the firmware is in `USAGE.md` §6. **Verify against the board** – this file was written
from the firmware and the picture, not from the PCB.

The encoder uses the same board: same pins, same 4051 codes; it drives the 4051 from a *clean* input instead of
from a coded one. Whether the analog path (levels, filters L1–L4) gives clean data-bit levels at the decoder's slicer
is the main open hardware question (see `USAGE.md` §7).

## Design files

* `Multiplatform CVBS Processor.sch` / `.brd` – schematic and board layout in the EAGLE format
  (the parts list contains the 4051, 4066, BS170 and the crystal of this design); `Multiplatform CVBS Processor.gif`
  is a picture of the board. 
