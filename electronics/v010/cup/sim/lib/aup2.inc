* Behavioural 74AUP1G86 (XOR) and 74AUP1G11 (3-input AND), same conventions as aup.inc (NOT vendor models).
.subckt aup_xor2 a b y vcc gnd params: undef=1
Bg yt gnd V = (v(vcc,gnd) > 0.8) ? (((v(a,gnd) > 0.5 * v(vcc,gnd)) != (v(b,gnd) > 0.5 * v(vcc,gnd))) ? v(vcc,gnd) : 0) : undef * v(vcc,gnd)
Ry yt y 25
Cy y gnd 1p
Ca a gnd 1p
Cb b gnd 1p
.ends aup_xor2

.subckt aup_and3 a b c y vcc gnd params: undef=1
Bg yt gnd V = (v(vcc,gnd) > 0.8) ? (((v(a,gnd) > 0.5 * v(vcc,gnd)) && (v(b,gnd) > 0.5 * v(vcc,gnd)) && (v(c,gnd) > 0.5 * v(vcc,gnd))) ? v(vcc,gnd) : 0) : undef * v(vcc,gnd)
Ry yt y 25
Cy y gnd 1p
Ca a gnd 1p
Cb b gnd 1p
Cc c gnd 1p
.ends aup_and3
