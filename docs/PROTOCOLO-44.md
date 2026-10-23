# JARVIS MARK XLIV — protocolo 44

O protocolo ativo anterior era 41 (MARK XLI), embora a pasta ainda fosse MARK-XL. Esta entrega organiza retrospectivamente as mudancas em tres etapas:

- 42: Voz e criacao — Fish Audio PT-BR prioritario; Gemini apenas apos falha do Fish; Studio ZeroGPU com duracao e arquivos de entrada.
- 43: Presenca 3D — Armadura 3D, reator e mascara rigida com luzes azuis; Mouse e comandos de voz para rotacao e iluminacao.
- 44: Interacao e escuta — Duas maos: zoom, mover, inclinar; punhos: girar; Supressao local de ruido mantendo volume e sensibilidade; Correcao de estabilidade COM e instancia unica.

Identidade central: core/protocol.json; carregada por actions/runtime_identity.py, interface e prompt de execucao.
Pasta principal: C:\Users\Sabrina\Desktop\MARK-XLIV.
As chaves MARK_XL de ambiente, o mutex de instancia e historicos antigos permanecem estaveis por compatibilidade.

Camera: abra Camera. Separe/junte as duas maos para zoom, mova-as juntas para deslocar, incline a linha entre elas para torcer. Feche os punhos para girar. Retire as maos para soltar. Mouse e comandos de voz continuam disponiveis.

Supressor RNNoise local apos o ganho e antes do envio ao reconhecimento. Nao altera VAD, volume do Windows ou a prioridade de voz Fish. Mantem fluxo continuo durante pausas. Se a biblioteca falhar, preserva a captura e registra o erro.


Sketchbook: desenhos com indicador apontado ou mouse, mao aberta para reposicionar, formas geometricas ajustadas, interpretacao Gemini nas pausas, Resetar e biblioteca em sketchbook/modelos (PNG + JSON editavel). Gerar imagem envia referencia e prompt ao Studio. A IA envia somente o desenho, com intervalo minimo de 5 segundos entre analises; cameras ficam locais. Modelos podem ser carregados e complementados depois.

A pasta fisica e MARK-XLIV. Os lancadores e o registro do Python apontam diretamente para ela; MARK-XL nao e necessaria. Atalho: JARVIS MARK XLIV.lnk.

Inicializacao pelo CMD: dentro de MARK-XLIV, use py main.py. O arquivo local py.cmd usa o Python da propria pasta por caminho relativo (%~dp0), evitando referencias antigas do lancador global. O atalho da area de trabalho usa diretamente esse mesmo Python.

Ajuste de voz e energia: recuperacao rapida de Gemini Live 1011, liberacao do dispositivo de audio ao reconectar, captura em blocos de 40 ms, RNNoise fora do loop de rede, Gemini Live sem espera de thinking e voz Fish por frases e suspensao local por "Jarvis desliga" / "Jarvis acorda". Reator vermelho parado durante suspensao, olhos apagados. Guia: docs/COMO_SUSPENDER_E_ACORDAR.md.

Spotify e gestos: nomes exibidos e IDs de dispositivos aceitos, controle de volume pela API, falhas sem desvio para outro aparelho; duas maos independentes no Sketchbook, punho fechado como borracha e alcance central ajustavel/calibravel; modo exclusivo Libras com sequencias de quatro segundos, sugestao revisavel e envio de texto ao Jarvis. Somente Libras envia quadros da camera ao Gemini mediante ativacao da interpretacao. Guia: docs/SPOTIFY_SKETCHBOOK_LIBRAS.md.
