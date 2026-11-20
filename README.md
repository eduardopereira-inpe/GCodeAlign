# PCB G-code Alignment Tool

Aplicação desktop local para corrigir exclusivamente a rotação 2D de trajetórias G-code de PCBs em torno da origem `(0, 0)`. Ela usa Tkinter e Matplotlib e não envia comandos à CNC, não se conecta ao GRBL/USB/serial e não implementa auto-leveling.

## Requisitos

- Python 3.10 ou superior.
- Tkinter (normalmente incluído no Python do Windows; em algumas distribuições Linux, instale o pacote `python3-tk`).
- Windows ou Linux com ambiente gráfico.

## Instalação

Após a publicação no PyPI, a aplicação poderá ser instalada com:

```bash
python -m pip install pcb-gcode-align
gcodealign
```

Para desenvolvimento local, crie um ambiente virtual:

```bash
python -m venv .venv
```

Ative o ambiente virtual e instale as dependências:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

```bash
# Linux/macOS
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Execução

Na raiz do projeto:

```bash
python run.py
```

Também é possível usar:

```bash
python -m pcb_alignment.main
```

Em uma instalação a partir do pacote, use o executável `gcodealign`.

## Empacotamento para PyPI

```bash
python -m pip install -e ".[dev]"
python -m build
python -m twine check dist/*
```

A publicação é um passo separado e requer credenciais do índice de destino.

## Fluxo de uso

1. Carregue um arquivo `.gcode`, `.nc` ou `.tap`.
2. Confira a trajetória original; a origem é sempre X0 Y0.
3. Selecione X ou Y conforme o eixo nominal do furo de referência.
4. Informe apenas as coordenadas medidas do segundo ponto, em milímetros.
5. Confira o sinal e o valor do ângulo de correção.
6. Ajuste o nome de saída, se necessário.
7. Salve o G-code transformado e continue o fluxo externo no UGS.

O nome sugerido recebe o sufixo `_rotated`. O arquivo original não pode ser selecionado como destino e nunca é sobrescrito automaticamente.

## Suporte G-code

A versão atual interpreta:

- G0 e G1, com coordenadas parciais e movimento modal;
- G2 e G3 com centros relativos I/J;
- G90/G91;
- G20/G21;
- comentários, Z, feed, spindle e comandos M preservados;
- comandos escritos de forma compacta ou separados por espaços.

A rotação preserva o sentido dos arcos. R, G90.1, G92, G10, planos G18/G19 e comandos geométricos não implementados bloqueiam a exportação com uma mensagem de linha. O programa prefere não gerar um arquivo a produzir uma trajetória potencialmente incorreta.

As coordenadas permanecem na unidade ativa de cada bloco. Internamente, a análise usa milímetros, sem alterar valores Z nem executar translação, escala, deformação ou correção por múltiplos pontos.

## Visualização

A visualização mostra G0, G1 e arcos da trajetória original e, após informar a referência, a trajetória transformada. A barra de navegação oferece pan, zoom e retorno à vista inicial; o botão **Ajustar à vista** recalcula os limites com proporção geométrica igual.

Leitura, análise, transformação, validação e gravação são executadas por um worker em background. A fila de mensagens mantém Tkinter e Matplotlib restritos à thread principal, enquanto barra de progresso e status são atualizados por `after()`. Novos parâmetros invalidam resultados anteriores, evitando que uma transformação obsoleta substitua o estado visível. Para reduzir o custo de arquivos grandes, os movimentos são preparados em trajetórias agregadas, em vez de criar um objeto gráfico por segmento.

## Testes

```bash
python -m pytest
```

O arquivo `examples/sample_board.gcode` pode ser usado para inspeção local. Ele é apenas um exemplo de software e não deve ser tratado como programa validado para qualquer máquina.

## Limitações e responsabilidade

A aplicação é um pré-processador geométrico. Compatibilidade com o controlador, unidades configuradas, origens de trabalho e trajetória final devem ser verificadas fora desta ferramenta. Nenhuma compatibilidade física com uma CNC é afirmada. Sempre valide o resultado em visualizador/simulador adequado antes de executar na máquina.
