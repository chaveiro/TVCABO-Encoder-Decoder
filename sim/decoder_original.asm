; alteração do burst 24 - 336
; alteração do video 24 - 337

	.device AT90S1200
	
	.equ	ACSR	= 0x08
	.equ	PIND	= 0x10
	.equ	DDRD	= 0x11
	.equ	PORTD	= 0x12
	.equ	PINB	= 0x16
	.equ	DDRB	= 0x17
	.equ	PORTB	= 0x18
	.equ	EECR	= 0x1C
	.equ	EEDR	= 0x1D
	.equ	EEAR	= 0x1E
	.equ	WDTCR	= 0x21
	.equ	TCNTO	= 0x32
	.equ	TIMER	= 0x32
	.equ	TCCRO	= 0x33
	.equ	MCUCR	= 0x35
	.equ	TIFR	= 0x38
	.equ	TIMSK	= 0x39
	.equ	GIMSK	= 0x3B

	.equ	EERE	= 0x00	; bit de ordem de leitura da EEPROM
	.equ	EEWE	= 0x01	; bit de ordem de escrita da EEPROM
	.equ	ACIE	= 0x03	; bit de interrupção do comparador
;registos para reconstrução do sinal
	.def	zonaA	= r0
	.def	zonaB	= r1
	.def	zonaB2	= r2
	.def	zonaC	= r3	
	.def	zonaD	= r4
	.def	zonaE	= r5
	.def	zonaF	= r6
	.def	zonaG	= r7
	.def	zonaH	= r8
;registos de leitura de sincronismo
	.def	osci	= r9	; 1º leitura de sincronismo
	.def	osc1	= r10	; 2º leitura de sincronismo
	.def	osc2	= r11	; 3º leitura de sincronismo
	.def	osc3	= r12	; 4º leitura de sincronismo
	.def	oscf	= r13	; 5º leitura de sincronismo
	.def	oscv	= r14	; 6º leitura de sincronismo
	.def	iref	= r15	; teste de mudança de canal
	.def	iref2	= r16
; registos para descodificação de imagem; 	
	.def	desco	= r17
	.def	video	= r18
	.def	burst	= r19
; registos de controle
	.def	flag	= r20	; flag's de controle
	.def	flgvco	= r21	; flag's de controle
	.def	ace	= r22	; valor para sincronização por software
	.def	linhal	= r23	; endereço baixo do contador de linhas
	.def	linhah	= r24	; endereço alto do contador de linhas
	.def	czona	= r25	; contador de linhas de cada zona
	.def	zona	= r26	; zona de quadro
	.def	csw	= r27	; contador para o switch da scart
	.def	falha	= r28
	.def	VportB	= r29	; valor de saida do PORTB
	.def	acet	= r30
	.def	temp	= r31	; temporário
; bit's do registo "zona"
	.equ	len	= 0x03	; = 0 - linha com 32uS
				; = 1 - linha com 64 uS
; bit's do registo "flag"
	.equ	video	= 0x00	; = 0 - video normal
				; = 1 - video invertido
	.equ	burst	= 0x01	; = 0 - burst normal
				; = 1 - burst invertido
	.equ	aosce	= 0x02	; = 0 - inicio da linha
				; = 1 - meio da linha
	.equ	data	= 0x03	; = 0 - linhas sem dados
				; = 1 - lêr informação de côr e imagem
	.equ	quadro	= 0x04	; = 0 - quadro par
				; = 1 - quadro impar
	.equ	iosc	= 0x05	; auxiliar de acerto do vcxo
	.equ	codif	= 0x07	; = 0 - sinal PAL
				; = 1 - sinal codificado
			
;bit's do registo "flgvco" - flag's do vcxo e sincronisação
	.equ	refi	= 0x00	; = 0 - espera 1º impulso de referência
				; = 1 - espera 2º impulso de referência
	.equ	pdup	= 0x01
	.equ	pddw	= 0x02				
	.equ	acerto	= 0x05	; valor do ultimo acerto do oscilador
	
; bits do ACSR
	.equ	sinc	= 0x05	; valor do sincronismo	
	.equ	bdata	= 0x05	; bit de dados
	
; bits' do registo "ace"

	.equ	bclamp	= 0x03	; = 0 - faz clamp
				; = 1 - não faz clamp
				
; bits do PORTB
	.equ	cdata	= 0x02	; saida para ligar o circuito de leitura de dados
	.equ	osc0	= 0x03	; saida para acerto da frequência dos oscilador
	.equ	clamp	= 0x04	; saida para clamp do sinal
	.equ	osc1	= 0x05	; saida 2 para acerto da frequência dos oscilador
	.equ	sw	= 0x06	; saida para selecção automática de SCART
	.equ	evco	= 0x07	; saida que dá o valor de estabilidade do vco
	
; valores de saida para o multiplexer
	.equ	vn	= 0x00	; vídeo normal
	.equ	vi	= 0x20	; vídeo invertido
	.equ	bn	= 0x00	; burst normal
	.equ	bi	= 0x10	; burst invertido
	.equ	pr	= 0x08	; preto
	.equ	sy	= 0x28	; sncronismo

; bit's do registo "falha"

	.equ	bfalha	= 0x02

; constantes
	.equ	vfalha	= exp2(bfalha)+3
				; nº de falhas de impulsos de referência até se
				; considerar mudança de canal
	.equ	mscart	= 0x00	; nº de quadros codificados para activação do 
				; sinal "SW". 


	
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
	sbrs	flag,codif
	rjmp	halfl		; ignora os impulsos de referencia se codificado
	sbrs	zona,len
	rjmp	tm4
	rjmp	halfl
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
leu1:	out	PORTD,zonaD
	ldi	temp,0x11
	sbrc	flag,data
	rjmp	ldata		; salta se for uma linha de dados
	sbrc	flag,aosce
	rjmp	halfl
	ldi	temp,3
	rcall	pausa		; 1,5 uS
	in	iref,ACSR	; lê 3º oscv
	out	PORTD,zonaE
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
	out	PORTD,zonaG
	rcall	pausa		; pausa de 0,9
	out	PORTD,zonaH

; detecta falha de canal se não houver sincronismo na posição osci e houver
; nas duas posições iref

	sbrc	flag,codif
	rjmp	ao0
	mov	iref,iref2
	rjmp	ao3
; procura sinal de mudança de canal
ao0:	mov	temp,oscv
	neg	temp
	or	iref,temp
ao3:	sbrs	iref,sinc
	rcall	cnorm		; detecta mudança de canal ou falha nos canais normais

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
	sbrc	flag,codif
	rjmp	des		; frequência central se não houver sincronismo num
				; sinal codificado
	sbr	flag,exp2(aosce)	; inverte indicação de posição de linha num 
				; canal normal
				
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
		
tmrex2:	sbrs	flag,codif
	rjmp	tmrex3		; salta para o temporizador de final de linha
tmrex8:	dec	czona
	breq	tmrex6
; identificação das linhas de leitura de dados e das linhas de correção de cor 
; e video
	cpi	zona,7
	breq	dat
	cpi	zona,8
	brne	tmtemp
	cpi	czona,3
	breq	corr2
	cpi	czona,2
	breq	corr
	cpi	czona,1
	breq	corr3
	rjmp	tmrex3
corr3:	sbrc	flag,quadro
	mov	zonaA,zonaH
	rjmp	tmrex3
; correção da cor e video
corr2:	sbrc	flag,quadro
	rjmp	tmrex3	
	rjmp	cb
corr:	ldi	temp,vn
	sbrc	flag,video
	ldi	temp,vi
	mov	zonaH,temp
cb:	ldi	temp,bn
	sbrc	flag,burst
	ldi	temp,bi
	mov	zonaF,temp
	rjmp	tmrex3
; activação do bit identificador de leitura de dados
dat:	ldi	temp,2
	sbrs	flag,quadro
	inc	temp
	cp	czona,temp
	brne	tmtemp
	sbr	flag,exp2(data)	
tmtemp:	rjmp	tmrex3

tmrex6:	inc	zona
	andi	zona,0x0F
	cpi	zona,0
	breq	zona0
	cpi	zona,1
	breq	zona1
	cpi	zona,2
	breq	zona2
	cpi	zona,8
	breq	zona8
	cpi	zona,9
	breq	zona9
	cpi	zona,10
	breq	zona10
	cpi	zona,11
	breq	zona11
	rjmp	zona12

; definição das zonas de imagem
zona0:	ldi	czona,5
	mov	zonaA,zonaB
	mov	zonaD,zonaB
	mov	zonaE,zonaB
	mov	zonaF,zonaB
	mov	zonaG,zonaB
	mov	zonaH,zonaB
	ldi	temp,sy
	mov	zonaC,temp
	rjmp	tmrex3
zona1:	ldi	temp,exp2(quadro)
	eor	flag,temp	; inverte o quadro
	dec	falha
	sbrs	falha,bfalha
	rcall	cnorm
	ldi	czona,5
	mov	zonaD,zonaC
	mov	zonaE,zonaC
	mov	zonaF,zonaC
	mov	zonaG,zonaC
	mov	zonaH,zonaC
	rjmp	tmrex3
zona2:	ldi	czona,5
	ori	zona,5
	mov	zonaD,zonaB
	mov	zonaE,zonaB
	mov	zonaF,zonaB
	mov	zonaG,zonaB
	mov	zonaH,zonaB
	rjmp	tmrex3
zona8:	ldi	czona,38
zona8a:	mov	zonaD,zonaC
	mov	zonaE,zonaB
	ldi	temp,bn
	mov	zonaF,temp
	mov	zonaG,zonaB
	mov	zonaH,zonaB
	rjmp	tmrex3
zona9:	mov	zonaA,zonaH
zona10:	rjmp	tmrex3
zona11:	ldi	czona,56
	rjmp	tmrex3
zona12:	andi	csw,0x1F
	cpi	csw,mscart
	brne	z14
	sbr	VportB,exp2(sw)
	rjmp	z13
z14:	inc	csw
z13:	ldi	czona,4
	mov	zonaA,zonaB
	ori	zona,15
	rjmp	zona8a
	
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

halfl:	clt
	sbrc	iref,sinc
	set
	sbrs	flag,codif
	rjmp	fn1
	sbrc	iref2,sinc
	set
fn1:	brts	fn
	ldi	falha,vfalha
fn:	sbrs	flgvco,refi	; verifica se encontrou o primeiro impulso
	rjmp	prim		; salta se espera o primeiro impulso
	cbr	flgvco,exp2(refi); indica que espera o primeiro impulso
	brtc	seg		; salta se encontrou tb o segundo 
	rjmp	clear		; erro se não houver 2º impulso

prim:	brts	prim3
	sbr	flgvco,exp2(refi) ;espera segundo impulso
prim3:	rjmp	incl3		; incrementa linha enquanto não encontrar o 1º impulso
	
seg:	cpi	linhah,2
	brne	comp2
	cpi	linhal,111
	brne	comp2
	sbr	flag,exp2(codif)
	clr	zona
	ldi	czona,5
	ldi	temp,pr
	mov	zonaA,temp
	mov	zonaB,temp
	mov	zonaD,temp
	mov	zonaE,temp
	mov	zonaF,temp
	mov	zonaG,temp
	mov	zonaH,temp
	ldi	temp,sy
	mov	zonaC,temp
	cbr	flag,exp2(quadro)
incl3:	rcall	incl		; incrementa uma linha
	rjmp	tmrex2

comp2:	cpi	linhah,1
	brne	clear
	cpi	linhal,80
	brne	clear
	rjmp	incl3

; encontrou um impulso fora de contage
clear:	ldi	linhah,1
	ldi	linhal,81
	rjmp	tmrex2

cnorm:	ldi	temp,vn		; define a imagem de saida igual à entrada
	mov	zonaA,temp
	mov	zonaB,temp
	mov	zonaC,temp
	mov	zonaD,temp
	mov	zonaE,temp
	mov	zonaF,temp
	mov	zonaG,temp
	mov	zonaH,temp
	out	PORTD,zonaA
	clr	zona
	clr	csw
	clr	linhah
	clr	linhal
	ldi	falha,vfalha
	cbr	flag,exp2(codif)
	cbr	VportB,exp2(sw)
	out	PORTB,VportB
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

; leitura e descodificação dos dados com a informação de cor e video

ldata:	cbr	flag,exp2(data); desliga o modo de leitura de dados
	
	mov	desco,temp
	mov	video,temp
	mov	burst,temp

	ldi	temp,22
	rcall	pausa
	sbi	PORTB,cdata

p0:	sbrc	osci,sinc
	rjmp	p1
p1:	sbrc	osc1,sinc
	rjmp	p2
p2:	sbrc	osc2,sinc
	rjmp	p3
p3:	sbrc	osc3,sinc
	rjmp	p4
p4:	sbrc	oscf,sinc
	rjmp	c1

; lê byte de descodificação
c1:	lsl	desco
	in	temp,ACSR
	bst	temp,bdata
	bld	desco,0x00	; lê bit de dados
	rjmp	c2
c2:	brcc	c1
c3:	lsl	desco
	in	temp,ACSR
	bst	temp,bdata
	bld	desco,0x00	; lê bit de dados
	rjmp	c4
c4:	brcc	c3

;lê byte de informação de video
c5:	lsl	video
	in	temp,ACSR
	bst	temp,bdata
	bld	video,0x00	; lê bit de dados
	rjmp	c6
c6:	brcc	c5
c7:	lsl	video
	in	temp,ACSR
	bst	temp,bdata
	bld	video,0x00	; lê bit de dados
	rjmp	c8
c8:	brcc	c7

;lê byte de informação de cor
c9:	lsl	burst
	in	temp,ACSR
	bst	temp,bdata
	bld	burst,0x00	; lê bit de dados
	rjmp	c10
c10:	brcc	c9
c11:	lsl	burst
	in	temp,ACSR
	bst	temp,bdata
	bld	burst,0x00	; lê bit de dados
	rjmp	c12
c12:	brcc	c11

	cbi	PORTB,cdata


aux3:	in	temp,TIFR
	sbrs	temp,1
	rjmp	aux3
	out	TIFR,temp

	rcall	pausar
	nop

	out	PORTD,zonaC
	ldi	temp,5
	rcall	pausa		; pausa de 2,1uS
	out	PORTD,zonaD

	eor	video,desco	; descodifica a informação de video
	eor	burst,desco	; descodifica a informação de cor

	
;interpreta a informação de video	
	clr	temp
c70:	lsr	video
	breq	c80
	brcc	c70
	inc	temp
	rjmp	c70
c80:	cbr	flag,exp2(video)
	subi	temp,0x04
	brsh	c7b
	sbr	flag,exp2(video)

;interpreta a informação de cor
c7b:	clr	temp
c7a:	lsr	burst
	breq	c8a
	brcc	c7a
	inc	temp
	rjmp	c7a
c8a:	cbr	flag,exp2(burst)
	subi	temp,0x04
	brsh	aux4
	sbr	flag,exp2(burst)

aux4:	ldi	ace,131

	rcall	incl
	ldi	temp,exp2(aosce)	
	eor	flag,temp	; inverte a indicação de posição na linha
	dec	czona
	rjmp	tmrex8

; pausa de (temp * 3 + 6) ciclos

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
	out	PORTD,temp	; video normal
	out	GIMSK,temp	; desliga as interrupções externas
	out	ACSR,temp	; liga a alimentação do comparador analógico e desliga 
				; a interrupção
	ldi	temp,0x01
	out	TCCRO,temp	; define o controle do timer com o CK (320 impulsos para 32uS)
	ldi	temp,2
	out	TIMSK,temp	; liga as interrupções do TIMER
	clr	flag
	rcall	cnorm		; define video de saida = video entrada (canal normal)
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

	.exit
