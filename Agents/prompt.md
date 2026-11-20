# Projeto: PCB G-code Alignment Tool

## Objetivo

Desenvolver uma aplicação desktop em Python para alinhamento geométrico de PCBs utilizadas em usinagem CNC, com o objetivo de corrigir pequenos desvios de rotação entre o sistema de coordenadas da PCB e o sistema de coordenadas da máquina.

A aplicação deve utilizar Tkinter como interface gráfica, Matplotlib para visualização das trajetórias e permitir carregar, visualizar, transformar e salvar arquivos G-code.

A aplicação será utilizada em conjunto com o FlatCAM, responsável pela geração do G-code, e o Universal G-code Sender (UGS), responsável pelo envio do arquivo à CNC e pela execução do auto-leveling.

O software não deve controlar diretamente a CNC, comunicar-se com o GRBL ou implementar o auto-leveling. Sua função é exclusivamente o pré-processamento geométrico do G-code.

---

## 1. Tecnologias e requisitos

- Python 3.
- Tkinter para interface gráfica.
- Matplotlib integrado ao Tkinter para visualização gráfica.
- NumPy, se necessário, para cálculos geométricos.
- Utilizar bibliotecas livres.
- Compatibilidade com Windows.
- Código organizado, modular e de fácil manutenção.
- Não utilizar frameworks GUI adicionais, como PyQt ou PySide.

A aplicação deve ser executada localmente, sem necessidade de conexão à internet, servidor, API ou banco de dados.

---

## 2. Premissas geométricas

O sistema assume que o usuário já estabeleceu mecanicamente o zero da PCB na máquina CNC.

A origem da PCB coincide com a origem definida na máquina:

PCB origin = Machine origin = (0, 0).

A origem não deve ser recalculada, deslocada ou alterada pela aplicação.

O problema a ser corrigido é exclusivamente a diferença angular entre os eixos da PCB e os eixos da máquina.

O usuário fará uma sondagem mecânica de dois pontos:

- Ponto A: origem da PCB, previamente definida como X0 Y0 na máquina.
- Ponto B: segundo furo de referência, cuja posição real será determinada por sondagem.

O usuário deverá informar apenas as coordenadas finais medidas do ponto B na máquina:

(x', y').

Não solicitar coordenadas do ponto A, pois ele é considerado fixo em (0, 0).

Não solicitar a distância nominal entre os dois furos, pois ela não é necessária para calcular a rotação quando o segundo ponto nominal está sobre um dos eixos coordenados.

---

## 3. Seleção do eixo de referência

A interface deverá possuir dois Radio Buttons mutuamente exclusivos:

- X: alinhamento utilizando um ponto de referência nominal sobre o eixo X da PCB.
- Y: alinhamento utilizando um ponto de referência nominal sobre o eixo Y da PCB.

A seleção representa o eixo nominal da PCB que deverá ser alinhado ao respectivo eixo da máquina.

### Referência X

O ponto nominal está sobre o eixo X:

P_nominal = (L, 0).

O usuário informa a posição medida:

P_measured = (x', y').

O sistema calcula a rotação necessária para alinhar o eixo nominal X ao eixo X da máquina.

### Referência Y

O ponto nominal está sobre o eixo Y:

P_nominal = (0, L).

O usuário informa a posição medida:

P_measured = (x', y').

O sistema calcula a rotação necessária para alinhar o eixo nominal Y ao eixo Y da máquina.

A origem permanece fixa em (0, 0) em ambos os casos.

O programa deve interpretar corretamente o sinal das coordenadas e calcular a rotação considerando os quadrantes, utilizando atan2, evitando ambiguidades de sinal.

Não realizar qualquer ajuste de translação da origem.

---

## 4. Transformação geométrica

Implementar uma transformação rígida 2D de rotação em torno da origem (0, 0).

Para o modo X, o ângulo observado do segundo ponto é:

theta_X = atan2(y', x').

O ângulo de correção deve ser o negativo do ângulo observado, de modo que o eixo nominal X seja alinhado ao eixo X da máquina.

Para o modo Y, o ângulo observado em relação ao eixo Y nominal é:

theta_Y = atan2(-x', y').

O ângulo de correção deve ser o negativo desse ângulo observado, de modo que o eixo nominal Y seja alinhado ao eixo Y da máquina.

Implementar a transformação:

X = x cos(theta) - y sin(theta)

Y = x sin(theta) + y cos(theta)

onde theta é o ângulo de correção calculado.

O ponto (0, 0) deve permanecer invariável.

O programa deverá exibir o ângulo calculado em graus, com precisão suficiente para avaliação de pequenos desvios.

Antes de implementar a matemática, verificar a consistência das convenções de coordenadas e validar os resultados com exemplos numéricos. Não assumir que a fórmula está correta apenas por ter sido especificada: confirmar que o ponto medido é levado ao eixo esperado e que a origem permanece fixa.

---

## 5. Interface gráfica

Criar uma interface organizada em uma única janela, utilizando Tkinter.

A interface deverá conter as seguintes áreas:

### 5.1 Arquivo de entrada

- Campo indicando o arquivo G-code carregado.
- Botão para abrir arquivo.
- Utilizar filedialog do Tkinter.
- Aceitar arquivos .gcode, .nc e .tap, além de permitir selecionar outros arquivos, se necessário.
- Exibir o nome do arquivo carregado.

### 5.2 Configuração do alinhamento

- Radio Button para eixo X.
- Radio Button para eixo Y.
- Campos numéricos para coordenadas X e Y medidas do segundo ponto.
- Coordenadas em milímetros.
- Aceitar valores negativos e decimais.
- Validar entradas.
- Atualizar a transformação quando os valores forem alterados ou quando o usuário solicitar atualização.

A origem é sempre considerada previamente definida em (0, 0).

### 5.3 Visualização gráfica do G-code

Integrar Matplotlib à interface Tkinter.

A visualização deve apresentar:

- Trajetória original.
- Trajetória transformada.
- Origem X0 Y0.
- Eixos X e Y.
- Grid.
- Proporção igual entre os eixos, utilizando aspect equal.
- Legenda diferenciando G-code original e transformado.

A trajetória original e a transformada devem ser visualizadas simultaneamente, permitindo avaliar o efeito da rotação.

Implementar controles básicos de navegação do gráfico:

- Zoom.
- Pan.
- Autoscale / Fit to view.

A visualização deve ser atualizada quando os parâmetros de alinhamento forem modificados.

Não é necessário implementar simulação 3D, visualização de ferramentas, profundidade de corte ou simulação física.

### 5.4 Informações da transformação

Exibir:

- Eixo selecionado.
- Coordenadas do ponto de referência medido.
- Ângulo de correção em graus.
- Status da transformação.
- Mensagens de erro ou validação.

A aplicação deverá apresentar claramente o ângulo aplicado, incluindo o sinal.

### 5.5 Arquivo de saída

Criar um campo editável contendo o nome do arquivo de saída.

O nome padrão deverá ser formado a partir do nome do arquivo original, acrescentando o sufixo:

_rotated

Exemplo:

board_top.gcode

board_top_rotated.gcode

O sufixo não deverá ser duplicado se o arquivo de entrada já possuir _rotated.

O usuário poderá editar o nome do arquivo de saída.

O botão de salvar deverá permitir selecionar o diretório de destino por meio de filedialog.

O arquivo original nunca deverá ser sobrescrito automaticamente.

---

## 6. Processamento do G-code

Implementar um parser capaz de interpretar o G-code produzido pelo FlatCAM.

O programa deverá preservar, sempre que possível:

- Comentários.
- Comandos de spindle.
- Feed rate.
- Comandos Z.
- Configurações de unidades.
- Configurações de coordenadas.
- Comandos de pausa.
- Comandos de início e término.
- Comandos não relacionados à geometria XY.

Transformar as coordenadas XY dos movimentos de modo que o G-code corresponda à nova orientação da PCB.

### Comandos de movimento

Inicialmente, priorizar:

- G0
- G1

O parser deverá identificar coordenadas X e Y em comandos de movimento e aplicar a transformação geométrica.

Deverá preservar corretamente os movimentos que especificam somente X ou somente Y, utilizando a posição anterior para reconstruir o ponto completo antes da transformação.

### Coordenadas absolutas e incrementais

Implementar suporte a:

- G90: coordenadas absolutas.
- G91: coordenadas incrementais.

A transformação geométrica deverá funcionar corretamente em ambos os modos.

No modo incremental, transformar os vetores de deslocamento, sem aplicar a translação da origem.

### Unidades

Preservar e tratar corretamente:

- G20: polegadas.
- G21: milímetros.

Internamente, se necessário, converter as coordenadas para uma unidade consistente, realizando a transformação e retornando ao formato original.

### Arcos

G2 e G3 não devem ser transformados incorretamente.

Se o suporte a arcos for implementado, transformar corretamente:

- Coordenadas finais X/Y.
- Coordenadas relativas do centro I/J.
- Sentido do arco, caso a transformação altere a orientação.

Como a transformação inicial é uma rotação, o sentido de G2/G3 deve ser preservado.

Caso o suporte a arcos não possa ser implementado de forma confiável na primeira versão, identificar explicitamente esses comandos e informar ao usuário. Não corromper silenciosamente o arquivo.

---

## 7. Visualização do G-code

A visualização deverá ser baseada na interpretação dos movimentos do arquivo.

Identificar movimentos de corte e movimentos rápidos, se possível.

Utilizar estilos distintos para:

- Movimentos rápidos G0.
- Movimentos de usinagem G1.
- Trajetória original.
- Trajetória transformada.

A visualização deverá manter a proporção geométrica correta e ser capaz de representar placas de diferentes dimensões.

O programa deverá permitir carregar o arquivo e visualizar a trajetória original mesmo antes de inserir os pontos de referência.

Quando os dados de alinhamento forem informados, atualizar automaticamente a trajetória transformada.

Se a transformação não tiver sido calculada, não exibir uma trajetória transformada fictícia.

---

## 8. Fluxo de utilização

O fluxo esperado da aplicação é:

1. Abrir o programa.
2. Carregar o G-code gerado pelo FlatCAM.
3. Visualizar a trajetória original.
4. Selecionar o eixo de referência X ou Y.
5. Informar X e Y do segundo ponto medido pela sonda.
6. Calcular a transformação.
7. Visualizar a trajetória original e a transformada.
8. Verificar o ângulo de correção.
9. Ajustar o nome do arquivo de saída, se necessário.
10. Salvar o G-code transformado.
11. Abrir o G-code resultante no UGS.
12. Executar o auto-leveling e a usinagem pelo fluxo normal do UGS.

---

## 9. Arquitetura do projeto

Organizar o código de forma modular.

Estrutura sugerida:

pcb_alignment/

    main.py

    gcode_parser.py

    alignment.py

    gcode_transform.py

    gcode_viewer.py

    requirements.txt

    README.md

Responsabilidades:

- main.py: interface Tkinter e fluxo da aplicação.
- gcode_parser.py: leitura e interpretação do G-code.
- alignment.py: cálculo do ângulo e transformação geométrica.
- gcode_transform.py: aplicação da transformação aos comandos G-code.
- gcode_viewer.py: visualização Matplotlib integrada ao Tkinter.
- requirements.txt: dependências externas.
- README.md: instalação, utilização e limitações.

A arquitetura pode ser modificada se o agente identificar uma organização mais simples e robusta, desde que a separação entre interface, matemática, parser e visualização seja mantida.

---

## 10. Robustez e validação

Implementar tratamento de erros para:

- Arquivo inválido.
- Arquivo vazio.
- G-code não reconhecido.
- Coordenadas inválidas.
- Campos numéricos vazios.
- Arquivo de saída inválido.
- Falha de leitura ou escrita.
- Comandos G-code não suportados.
- Movimentos com coordenadas incompletas.
- Alteração de unidades.
- Coordenadas incrementais.

Não permitir salvar o resultado se os parâmetros de alinhamento forem inválidos.

Não modificar o arquivo original.

Não assumir que todas as linhas do G-code contêm coordenadas XY.

Preservar linhas que não necessitam de transformação.

---

## 11. Testes

Criar testes automatizados para a transformação geométrica e o parser.

### Teste 1 — Sem rotação

Ponto medido sobre o eixo de referência, sem desvio angular.

Resultado esperado: theta = 0° e trajetória inalterada.

### Teste 2 — Pequena rotação positiva

Simular um ponto de referência deslocado angularmente em relação ao eixo nominal.

Resultado esperado: a transformação corrige o ângulo e alinha o eixo nominal com o eixo da máquina.

### Teste 3 — Pequena rotação negativa

Resultado esperado: correção no sentido oposto, sem inversão indevida.

### Teste 4 — Origem

Resultado esperado: (0, 0) permanece invariável.

### Teste 5 — Modo X

O segundo ponto corrigido deverá ficar sobre o eixo X.

### Teste 6 — Modo Y

O segundo ponto corrigido deverá ficar sobre o eixo Y.

### Teste 7 — G-code absoluto

Transformar corretamente trajetórias G0 e G1 utilizando G90.

### Teste 8 — G-code incremental

Transformar corretamente os deslocamentos utilizando G91.

### Teste 9 — Preservação de Z

Nenhuma coordenada Z deve ser alterada.

### Teste 10 — Preservação de comandos

M3, M5, F, S, comentários e outros comandos não relacionados à transformação XY devem ser preservados.

### Teste 11 — Arquivo de saída

Verificar a geração correta do nome _rotated e impedir sobrescrita automática do original.

---

## 12. Entregáveis

Implementar o projeto completo e entregar:

1. Código Python funcional.
2. Todos os módulos necessários.
3. requirements.txt.
4. README.md com instruções de instalação e execução.
5. Testes automatizados da transformação.
6. Interface gráfica funcional.
7. Visualização das trajetórias original e transformada.
8. Exemplo de G-code para testes, caso necessário.

O código deverá estar pronto para execução local no VS Code.

---

## 13. Diretrizes de implementação

Priorizar:

- Simplicidade.
- Robustez.
- Clareza.
- Facilidade de manutenção.
- Precisão geométrica.
- Interface funcional.
- Compatibilidade com G-code gerado pelo FlatCAM.
- Facilidade de evolução futura.

Não implementar funcionalidades desnecessárias.

Não desenvolver integração com UGS nesta etapa.

Não implementar controle da CNC.

Não implementar auto-leveling.

Não implementar câmera ou visão computacional.

Não implementar transformação de escala, deformação, cisalhamento ou correção baseada em múltiplos pontos.

A primeira versão deve resolver exclusivamente o alinhamento angular XY com origem fixa.

Antes de concluir, executar os testes automatizados e verificar a consistência matemática das transformações, especialmente a seleção dos eixos X/Y e os sinais dos ângulos de correção.

Caso alguma funcionalidade especificada seja tecnicamente incompatível com o G-code gerado pelo FlatCAM, documentar a limitação e implementar uma alternativa segura, sem corromper o arquivo original.

### Observação crítica sobre a integridade do G-code

A transformação do G-code deve ser implementada com extremo cuidado. Não basta localizar e substituir valores de X e Y nas linhas do arquivo, pois isso pode comprometer silenciosamente a geometria das trajetórias. O parser deverá considerar corretamente os modos de coordenadas absolutas e incrementais (G90/G91), unidades (G20/G21), movimentos com coordenadas parciais, posição acumulada da ferramenta e comandos de arco (G2/G3), incluindo seus parâmetros I/J. Antes de aplicar qualquer transformação, o agente deverá avaliar a compatibilidade do arquivo com os recursos efetivamente implementados. Caso encontre comandos, estruturas ou condições que não possam ser transformados com segurança, deverá identificá-los explicitamente e bloquear a exportação do G-code transformado, informando ao usuário o motivo. **É preferível não gerar um arquivo a gerar um G-code aparentemente válido, mas com trajetórias incorretas que possam causar danos à PCB, à ferramenta ou à máquina.** O arquivo original deverá permanecer intacto, e a integridade do resultado deverá ser validada antes de permitir sua exportação.