; key.inc - EEPROM image of the shared key (4 bytes).
; Default: all 0xFF = erased EEPROM = STANDARD MODE (no key).
; Create a real key with tools/keytool.py (see USAGE.md). Never commit a real key.
	.eseg
	.org	0
	.db	0xFF,0xFF,0xFF,0xFF
	.cseg
