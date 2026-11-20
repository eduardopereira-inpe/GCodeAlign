; Exemplo seguro de placa (sem conexão com hardware)
G21
G90
G17
G0 X0 Y0 Z5
G1 Z-0.1 F120
G1 X20 Y0
G1 X20 Y15
G2 X15 Y20 I-5 J0
G1 X0 Y20
G1 X0 Y0
G0 Z5
M5
