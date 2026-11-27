# sim/
`avr.py` – minimal AT90S1200 emulator + AVRASM-dialect assembler (cycle-exact for the instructions used, Timer0, comparator, EEPROM read stall).
`harness.py` – encoder -> coded waveform -> decoder closed loop with a simple VCXO/analog model.
`sig.py` – clean PAL line/frame generator. `decoder_original.asm` – the original, unpatched decoder (reference for the bit-exact test).
Software models only: they say nothing about real analog behaviour.
