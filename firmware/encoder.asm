; =====================================================================
; ENCODER for the V41 / TVRabo board (AT90S1200 @ 10 MHz, same hardware)
; Companion of decoder.asm: produces the "coded" PAL that it decodes.
; GENERATED FILE: edit firmware/encoder.tpl and run tools/gen_encoder.py
;
; Coded signal (what the existing decoder needs, derived from its code):
;  * every line: regenerated 4.6 us sync, black, burst window (bn/bi),
;    video window (vn/vi). No broad/equalizing pulses are sent.
;  * reference pairs (sync-level pulse from +14 us to +59 us after the
;    line start): lines 335+336 (pair A) and 622+623 (pair B). The decoder
;    counts lines (counter = line number) and enters coded mode on pair B.
;  * data lines 5 and 317: 24 bits, 0.8 us each (bit 1 = black, bit 0 =
;    sync level), bytes n, V^K', B^K'. popcount >= 5 -> normal, <= 4 ->
;    inverted. Pattern sent: 0xFF (normal) or 0x00 (inverted).
;  * video inverted from line 24..308 (field 1) / 337..621 (field 2),
;    selected by the 2 flag bits of the data line. The 4 combinations
;    (video, burst) rotate field by field; nonce n advances by 0x3B.
;  * [KEY] K' = F(n) with the KEYLEN-byte key in EEPROM[0..KEYLEN-1]; erased EEPROM
;    (all 0xFF) gives F = identity = STANDARD mode (K' = n), exactly the
;    original coded signal. See docs/PROTOCOL.md.
; Frame sync comes from the input VBI: 3 broad line starts = field 1,
; 2 = field 2. Output starts after 3 consistent fields.
; Hardware stack use: 3 of 3 levels (limit!). Size: see README.
; Verified only in an emulator, not on real hardware.
; =====================================================================
	.device AT90S1200
	
	.equ	ACSR	= 0x08
	.equ	DDRD	= 0x11
	.equ	PORTD	= 0x12
	.equ	DDRB	= 0x17
	.equ	PORTB	= 0x18
	.equ	EECR	= 0x1C
	.equ	EEDR	= 0x1D
	.equ	EEAR	= 0x1E
	.equ	WDTCR	= 0x21
	.equ	TIMER	= 0x32
	.equ	TCCRO	= 0x33
	.equ	TIFR	= 0x38
	.equ	TIMSK	= 0x39
	.equ	GIMSK	= 0x3B

	.equ	EERE	= 0x00
	.equ	KEYLEN	= 4	; [KEY] key length in bytes (EVEN; limited by the decoder ISR time budget, 6 = 12 cycle margin)
;registos para reconstrução do sinal
	.def	zonaA	= r0	; mux code at start of every section
	.def	zonaB	= r1	; constant: black
	.def	zonaB2	= r2
	.def	zonaC	= r3	; constant: sync
	.def	zonaI	= r4	; mux code at cycle 186 of line-start section
	.def	kpre	= r5	; [KEY] mask actually used for V and B (computed by kmix from kreg)
	.def	zonaF	= r6	; burst window code
	.def	zonaAm	= r7	; code for the mid-line section A
	.def	zonaH	= r8	; video window code
;registos de leitura de sincronismo
	.def	osci	= r9	; 1º leitura de sincronismo
	.def	osc1	= r10	; 2º leitura de sincronismo
	.def	osc2	= r11	; 3º leitura de sincronismo
	.def	osc3	= r12	; 4º leitura de sincronismo
	.def	oscf	= r13	; 5º leitura de sincronismo
	.def	oscv	= r14	; 6º leitura de sincronismo
	.def	iref	= r15	; teste de mudança de canal
	.def	iref2	= r16
; registos para codificação de imagem; 	
	.def	datak	= r17	; data byte 1: nonce n
	.def	datav	= r18	; data byte 2: video info (xor key)
	.def	datab	= r19	; data byte 3: burst info (xor key)
; registos de controle
	.def	flag	= r20	; flag's de controle
	.def	flgvco	= r21	; flag's de controle
	.def	ace	= r22	; valor para sincronização por software
	.def	linhal	= r23	; endereço baixo do contador de linhas
	.def	linhah	= r24	; endereço alto do contador de linhas
	.def	seqn	= r25	; field counter (selects inversion pattern)
	.def	kreg	= r26	; running nonce (sent in clear as data byte 1)
	.def	bcnt	= r27	; consecutive broad-pulse line starts seen
	.def	conf	= r28	; frame-sync confidence (0..3)
	.def	VportB	= r29	; valor de saida do PORTB
	.def	acet	= r30
	.def	temp	= r31	; temporário

; bit's do registo "flag"
	.equ	video	= 0x00	; = 0 - video normal
				; = 1 - video invertido
	.equ	burst	= 0x01	; = 0 - burst normal
				; = 1 - burst invertido
	.equ	aosce	= 0x02	; = 0 - inicio da linha
				; = 1 - meio da linha
	.equ	data	= 0x03	; = 0 - linhas sem dados
				; = 1 - lêr informação de côr e imagem
	.equ	iosc	= 0x05	; auxiliar de acerto do vcxo
	.equ	vprv	= 0x06	; mid-line video was active on the previous line
; bits of "flgvco"
	.equ	pdup	= 0x01
	.equ	pddw	= 0x02				
	.equ	acerto	= 0x05	; valor do ultimo acerto do oscilador
	
; bits do ACSR
	.equ	sinc	= 0x05	; valor do sincronismo	
	
; bits' do registo "ace"

	.equ	bclamp	= 0x03	; = 0 - faz clamp
				; = 1 - não faz clamp
				
; bits do PORTB
	.equ	osc0	= 0x03	; saida para acerto da frequência dos oscilador
	.equ	clamp	= 0x04	; saida para clamp do sinal
	.equ	evco	= 0x07	; saida que dá o valor de estabilidade do vco
	
; valores de saida para o multiplexer
	.equ	vn	= 0x00	; vídeo normal
	.equ	vi	= 0x20	; vídeo invertido
	.equ	bn	= 0x00	; burst normal
	.equ	bi	= 0x10	; burst invertido
	.equ	pr	= 0x08	; preto
	.equ	sy	= 0x28	; sncronismo
; data-bit levels: bit 1 -> dhi, bit 0 -> dlo
	.equ	dhi	= pr
	.equ	dlo	= sy
; line numbers (PAL 625)
	.equ	F1A	= 24	; first line with video, field 1
	.equ	F1B	= 308	; last line with video, field 1
	.equ	F2A	= 337
	.equ	F2B	= 621	; (line 621 has video only up to the line-start section)


	
	.org 0
	
; endereços das rotinas de interrupção	
reset:	rjmp	main		; salta para o inicio do programa
	nop
tmrovr:	rjmp	tmrov		; salta para a rotina de interrupção de timer overflow

tmrov:	out	PORTD,zonaA
	mov	zonaB2,zonaB
	sbrc	flag,aosce	; verifica se está no principio da linha ou no meio
	mov	zonaB2,zonaA
	mov	temp,flag
	andi	temp,exp2(iosc)
	eor	flgvco,temp
	sbrc	flgvco,acerto
	rjmp	uma
	cbr	VportB,exp2(osc0)
	rjmp	f1
uma:	sbr	VportB,exp2(osc0)
	nop
f1:	out	PORTB,VportB	; acerto do VCO


	ldi	temp,1
	rcall	pausar		; pausa de 0,7 uS



	in	iref,ACSR	; verifica impulso de referência
	out	PORTD,zonaB2
	sbrs	flag,aosce
	rjmp	tm2	
	rjmp	midl
tm2:	rjmp	tm2a
tm2a:	rjmp	tm4
tm4:	rjmp	tm4a
tm4a:	nop
	in	osci,ACSR
	in	osc1,ACSR
	in	osc2,ACSR
	in	osc3,ACSR
	in	oscf,ACSR
	rcall	pausar
	in	oscv,ACSR	; verifica se o sincronismo está atrasado
	out	PORTD,zonaC
	sbrc	oscv,sinc
	rjmp	ler2
	ldi	temp,3
	rcall	pausa		; pausa de 1,8 uS
	rjmp	al
al:	rjmp	leu1
ler2:	rcall	pausar		; pausa de 0,7 uS
	in	osci,ACSR
	in	osc1,ACSR
	in	osc2,ACSR
	in	osc3,ACSR
	rcall	pausar
	in	oscv,ACSR
leu1:	out	PORTD,zonaC
	ldi	temp,0x11
	nop
	nop
	nop
	nop
	ldi	temp,3
	rcall	pausa		; 1,5 uS
	in	iref,ACSR	; lê 3º oscv
	out	PORTD,zonaB
	sbrs	oscv,sinc
	rjmp	nacer
	sbrs	iref,sinc
	subi	ace,24
	rjmp	nacer2
nacer:	rjmp	nacer4
nacer4:	nop
nacer2:	and	oscv,iref	; actualiza oscv se houver acerto
	out	PORTD,zonaF
	neg	iref
	rcall	pausar
	sbrs	ace,bclamp
	sbi	PORTB,clamp
	in	temp,ACSR
	or	iref,temp
	ldi	temp,6
	rcall	pausa		; pausa de 2,4 uS
	nop
	in	iref2,ACSR
	or	iref,iref2	; produz leitura válida para falha de canal
	ldi	temp,1
	cbi	PORTB,clamp
	out	PORTD,zonaB
	rcall	pausa		; pausa de 0,9
	out	PORTD,zonaH
	sbrc	flag,data
	rjmp	dline
	ldi	temp,7
	rcall	pausa
	out	PORTD,zonaI

; PLL ladder (identical to the decoder, non-coded branch)
ao2:	cbr	flag,exp2(iosc)
	sbrs	osci,sinc
	ldi	ace,196		; sinal muito adiantado, acerto por software
	sbrs	osc1,sinc
	rjmp	um		; sinal adiantado, aumenta frequência do oscilador
	sbrs	osc2,sinc
	rjmp	des		; sinal sincronizado, mantem frequência
	sbrs	osc3,sinc
	rjmp	zero		; sinal atrasado, diminui frequência
	sbrs	oscv,sinc
	rjmp	ao1		; sinal muito atrasado, acerto por software
	sbr	flag,exp2(aosce)

ao1:	sbr	flgvco,exp2(pddw)
	ldi	ace,194
zero:	cbr	VportB,exp2(evco)	; indicador de estabilidade do VCO
	cbr	flgvco,exp2(acerto)
	cbr	flgvco,exp2(pdup)	
	rjmp	tmrex2

des:	sbrc	flgvco,pdup
	rjmp	tmrex2
	sbrc	flgvco,pddw
	rjmp	tmrex2
	sbr	VportB,exp2(evco)	; indicador de estabilidade do VCO
	sbr	flag,exp2(iosc)
	rjmp	tmrex2

um:	cpi	ace,196
	brne	umaa
	sbr	flgvco,exp2(pdup)	
umaa:	cbr	VportB,exp2(evco)	; indicador de estabilidade do VCO
	sbr	flgvco,exp2(acerto)
	cbr	flgvco,exp2(pddw)	
		
tmrex2:	mov	zonaA,zonaAm	; A code for the mid-line section
	
tmrex3:	in	temp,TIFR
	sbrs	temp,1
	rjmp	tmrex3
	out	TIFR,temp
	
	
	in	iref2,ACSR

	; define o comprimento da próxima secção

t3:	in	temp,TIMER
	add	temp,ace
	out	TIMER,temp
	ldi	ace,195
t4:	reti

; ---------------------------------------------------------------------
; mid-line section: frame detection + preparation of the next line
; ---------------------------------------------------------------------
midl:	sbrs	iref2,sinc	; iref2 = sample 22us after the line-start edge
	rjmp	bro		; sync level -> broad pulse at line start
	tst	bcnt
	breq	mnext
	cpi	bcnt,3		; 3 broad line starts = field 1 (lines 1-3)
	brne	m2
	cpi	linhal,4	; current line should be 4
	brne	bad1
	tst	linhah
	brne	bad1
	rjmp	good
bad1:	clr	conf
	clr	linhah
	ldi	linhal,4
	rjmp	clrb
m2:	cpi	bcnt,2		; 2 broad line starts = field 2 (lines 314,315)
	brne	clrb
	cpi	linhal,60	; current line should be 316
	brne	bad2
	cpi	linhah,1
	brne	bad2
	rjmp	good
bad2:	clr	conf
	ldi	linhah,1
	ldi	linhal,60
	rjmp	clrb
good:	cpi	conf,3
	brsh	clrb
	inc	conf
clrb:	clr	bcnt
	rjmp	mnext
bro:	cpi	bcnt,7
	brsh	mnext
	inc	bcnt
mnext:	rcall	nextline
	rjmp	tmrex3

; ---------------------------------------------------------------------
; nextline: advance the line counter and compute codes for that line
; ---------------------------------------------------------------------
nextline:
	rcall	incl
	bst	flag,vprv	; T = mid-line video was active on the previous line
	clr	acet		; bit0 video, bit1 pulse line, bit2 data line, bit3 mid-line video
	cpi	conf,3
	brlo	nl_codes
	cpi	linhal,low(F1A)
	ldi	temp,high(F1A)
	cpc	linhah,temp
	brlo	r2chk
	cpi	linhal,low(F1B+1)
	ldi	temp,high(F1B+1)
	cpc	linhah,temp
	brlo	setvid
r2chk:	cpi	linhal,low(F2A)
	ldi	temp,high(F2A)
	cpc	linhah,temp
	brlo	nov
	cpi	linhal,low(F2B+1)
	ldi	temp,high(F2B+1)
	cpc	linhah,temp
	brsh	nov
setvid:	sbr	acet,1
	sbr	acet,8		; bit3: video also in the mid-line section ...
	cpi	linhah,2
	brne	nov
	cpi	linhal,low(F2B)	; ... except on the last line of field 2
	brne	nov
	cbr	acet,8
nov:	cpi	linhah,1	; reference pulse lines 335,336,622,623
	brne	pl2
	cpi	linhal,79
	breq	ispl
	cpi	linhal,80
	breq	ispl
	rjmp	pl3
pl2:	cpi	linhah,2
	brne	pl3
	cpi	linhal,110
	breq	ispl
	cpi	linhal,111
	brne	pl3
ispl:	sbr	acet,2
pl3:	cpi	linhah,0	; data lines 5 and 317
	brne	dl2
	cpi	linhal,5
	breq	isdl
	rjmp	nl_codes
dl2:	cpi	linhah,1
	brne	nl_codes
	cpi	linhal,61
	brne	nl_codes
isdl:	sbr	acet,4
nl_codes:
	ldi	temp,vn
	sbrc	flag,video
	ldi	temp,vi
	mov	zonaH,zonaB
	sbrc	acet,0
	mov	zonaH,temp
	mov	zonaA,zonaB
	brtc	nl2
	mov	zonaA,temp	; tail of the previous line's video
nl2:	mov	zonaAm,zonaB
	sbrc	acet,3
	mov	zonaAm,temp
	mov	zonaI,zonaH
	sbrs	acet,1
	rjmp	nl3
	mov	zonaAm,zonaC
	mov	zonaI,zonaC
nl3:	mov	zonaF,zonaB
	sbrs	acet,0
	rjmp	nl4
	ldi	temp,bn
	sbrc	flag,burst
	ldi	temp,bi
	mov	zonaF,temp
nl4:	cbr	flag,exp2(vprv)
	sbrc	acet,3
	sbr	flag,exp2(vprv)
	sbrs	acet,2
	ret
; data line coming: choose inversion pattern and build the 3 bytes
	inc	seqn
	cbr	flag,(exp2(video)|exp2(burst))
	sbrc	seqn,0
	sbr	flag,exp2(video)
	sbrc	seqn,1
	sbr	flag,exp2(burst)
	mov	datak,kreg	; nonce; kpre was prepared (F(kreg)) in the previous data ISR
	ldi	temp,0xFF
	sbrc	flag,video
	clr	temp
	eor	temp,kpre
	mov	datav,temp
	ldi	temp,0xFF
	sbrc	flag,burst
	clr	temp
	eor	temp,kpre
	mov	datab,temp
	sbr	flag,exp2(data)
	ret

;incrementa uma linha	
incl:	inc	linhal
	brne	lc3
	inc	linhah
lc3:	cpi	linhah,2
	brne	lc4
	cpi	linhal,114
	breq	lc7
lc4:	ret
lc7:	clr	linhah
	ldi	linhal,1
	ret

; ---------------------------------------------------------------------
; data line: 24 bits, 0.8 us per bit, timed to match the decoder sampling
; ---------------------------------------------------------------------
dline:	cbr	flag,exp2(data); desliga o modo de leitura de dados
	rcall	pausar	; 7 cycles
	rjmp	w1
w1:
	nop
	ldi	temp,dlo
	sbrc	datak,7
	ldi	temp,dhi
	out	PORTD,temp	; bit 0
	rjmp	w2
w2:
	rjmp	w3
w3:
	ldi	temp,dlo
	sbrc	datak,6
	ldi	temp,dhi
	out	PORTD,temp	; bit 1
	rjmp	w4
w4:
	rjmp	w5
w5:
	ldi	temp,dlo
	sbrc	datak,5
	ldi	temp,dhi
	out	PORTD,temp	; bit 2
	rjmp	w6
w6:
	rjmp	w7
w7:
	ldi	temp,dlo
	sbrc	datak,4
	ldi	temp,dhi
	out	PORTD,temp	; bit 3
	rjmp	w8
w8:
	nop
	ldi	temp,dlo
	sbrc	datak,3
	ldi	temp,dhi
	out	PORTD,temp	; bit 4
	rjmp	w9
w9:
	rjmp	w10
w10:
	ldi	temp,dlo
	sbrc	datak,2
	ldi	temp,dhi
	out	PORTD,temp	; bit 5
	rjmp	w11
w11:
	rjmp	w12
w12:
	ldi	temp,dlo
	sbrc	datak,1
	ldi	temp,dhi
	out	PORTD,temp	; bit 6
	rjmp	w13
w13:
	rjmp	w14
w14:
	ldi	temp,dlo
	sbrc	datak,0
	ldi	temp,dhi
	out	PORTD,temp	; bit 7
	rjmp	w15
w15:
	nop
	ldi	temp,dlo
	sbrc	datav,7
	ldi	temp,dhi
	out	PORTD,temp	; bit 8
	rjmp	w16
w16:
	rjmp	w17
w17:
	ldi	temp,dlo
	sbrc	datav,6
	ldi	temp,dhi
	out	PORTD,temp	; bit 9
	rjmp	w18
w18:
	rjmp	w19
w19:
	ldi	temp,dlo
	sbrc	datav,5
	ldi	temp,dhi
	out	PORTD,temp	; bit 10
	rjmp	w20
w20:
	rjmp	w21
w21:
	ldi	temp,dlo
	sbrc	datav,4
	ldi	temp,dhi
	out	PORTD,temp	; bit 11
	rjmp	w22
w22:
	nop
	ldi	temp,dlo
	sbrc	datav,3
	ldi	temp,dhi
	out	PORTD,temp	; bit 12
	rjmp	w23
w23:
	rjmp	w24
w24:
	ldi	temp,dlo
	sbrc	datav,2
	ldi	temp,dhi
	out	PORTD,temp	; bit 13
	rjmp	w25
w25:
	rjmp	w26
w26:
	ldi	temp,dlo
	sbrc	datav,1
	ldi	temp,dhi
	out	PORTD,temp	; bit 14
	rjmp	w27
w27:
	rjmp	w28
w28:
	ldi	temp,dlo
	sbrc	datav,0
	ldi	temp,dhi
	out	PORTD,temp	; bit 15
	rjmp	w29
w29:
	nop
	ldi	temp,dlo
	sbrc	datab,7
	ldi	temp,dhi
	out	PORTD,temp	; bit 16
	rjmp	w30
w30:
	rjmp	w31
w31:
	ldi	temp,dlo
	sbrc	datab,6
	ldi	temp,dhi
	out	PORTD,temp	; bit 17
	rjmp	w32
w32:
	rjmp	w33
w33:
	ldi	temp,dlo
	sbrc	datab,5
	ldi	temp,dhi
	out	PORTD,temp	; bit 18
	rjmp	w34
w34:
	rjmp	w35
w35:
	ldi	temp,dlo
	sbrc	datab,4
	ldi	temp,dhi
	out	PORTD,temp	; bit 19
	rjmp	w36
w36:
	nop
	ldi	temp,dlo
	sbrc	datab,3
	ldi	temp,dhi
	out	PORTD,temp	; bit 20
	rjmp	w37
w37:
	rjmp	w38
w38:
	ldi	temp,dlo
	sbrc	datab,2
	ldi	temp,dhi
	out	PORTD,temp	; bit 21
	rjmp	w39
w39:
	rjmp	w40
w40:
	ldi	temp,dlo
	sbrc	datab,1
	ldi	temp,dhi
	out	PORTD,temp	; bit 22
	rjmp	w41
w41:
	rjmp	w42
w42:
	ldi	temp,dlo
	sbrc	datab,0
	ldi	temp,dhi
	out	PORTD,temp	; bit 23
	rcall	pausar	; 7 cycles
	out	PORTD,zonaB	; back to black

	in	temp,TIFR	; clear TOV#2 right after the bits (idle time follows)
	out	TIFR,temp
	ldi	temp,exp2(aosce)
	eor	flag,temp	; this ISR covers two sections
	rcall	nextline
	ldi	temp,0x3B	; [KEY] prepare nonce and mask for the NEXT data line
	add	kreg,temp
	rcall	kmix
	ldi	ace,131
	rjmp	tmrex3

; [KEY] kpre := mask for the data line, derived from the nonce kreg.
; The decoder samples 3 bit-times before the first transmitted bit, so its
; first register ("desco") holds 111 + the top 5 bits of the nonce:
;     desco = 0xE0 | (kreg >> 3)
; and it then computes  M = F(desco)  with the key in EEPROM:
;     for i = KEYLEN-1..0:  t = key[i] + 1 ; X = swap(X + t) ^ t
; Only the low 5 bits of M are compared against the first 5 bits of the V and B
; bytes (the rest of those bytes is nonce/free bits), so the encoder sends
; V = B-pattern ^ rol3(M)  (rol3 puts M[4:0] at bit positions 7..3).
; key = FF*KEYLEN (erased EEPROM) -> t = 0 -> swap^KEYLEN (KEYLEN even) = identity
;   -> M = desco -> STANDARD mode (same classes as the original coded signal).
kmix:	mov	kpre,kreg
	lsr	kpre
	lsr	kpre
	lsr	kpre
	ldi	temp,0xE0
	or	kpre,temp
	ldi	acet,KEYLEN-1
km1:	out	EEAR,acet
	sbi	EECR,EERE
	in	temp,EEDR
	inc	temp
	add	kpre,temp
	swap	kpre
	eor	kpre,temp
	dec	acet
	brpl	km1
	swap	kpre		; rol3 = swap (rol4) then ror1
	bst	kpre,0
	lsr	kpre
	bld	kpre,7
	ret

pausa:	dec	temp
	brne	pausa
pausar:	ret
	
; rotinas de inicialização do processador
main:	cli			; desliga todas as interrupções
	wdr			; reset ao watchdog antes da activação
	ldi	temp,0x08
	out	WDTCR,temp	; liga o watchdog com 16mS
	ldi	temp,0x38
	out	DDRD,temp	; define as entradas e saídas do PORTD
	ldi	temp,0xFC
	out	DDRB,temp	; define as entradas e saidas do PORTB
	clr	VportB
	out	PORTB,VportB
	clr	temp
	out	GIMSK,temp	; desliga as interrupções externas
	out	ACSR,temp	; liga a alimentação do comparador analógico e desliga 
				; a interrupção
	ldi	temp,pr
	mov	zonaA,temp
	mov	zonaB,temp
	mov	zonaAm,temp
	mov	zonaF,temp
	mov	zonaH,temp
	mov	zonaI,temp
	out	PORTD,temp	; video normal
	ldi	temp,sy
	mov	zonaC,temp
	clr	flag
	clr	flgvco
	clr	linhah
	clr	linhal
	clr	bcnt
	clr	conf
	clr	seqn
	ldi	temp,0x3B	; first nonce
	mov	kreg,temp
	rcall	kmix	; [KEY] mask for the first data line (before sei)
	ldi	temp,0x01
	out	TCCRO,temp	; define o controle do timer com o CK (320 impulsos para 32uS)
	ldi	temp,2
	out	TIMSK,temp	; liga as interrupções do TIMER
	ldi	ace,195

; ciclo infinito de linhas de 32 uS
	
	sei			; liga as interrupções (timer)
int3:	in	temp,TIMER	; verifica o valor do TIMER
	cpi	temp,249	; verifica se chegou a 249
	brlo	int3		; repete o ciclo até que TIMER seja >= 249
;rotina de acerto do vcxo
	nop			; pausa de nop's para garantir que a interrupção
	nop			; seja numa intrução de 1 ciclo
	nop
	nop
	nop
	nop
	wdr			; reset do watchdog, todas as meias linhas
	ldi	temp,exp2(aosce)	
	eor	flag,temp	; inverte a indicação de posição na linha
	rjmp	int3

	.include "key.inc"

	.exit				
	
	