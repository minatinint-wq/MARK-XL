# Sketchbook e Estúdio de Música — 10/09/2026

## Editar objetos com as mãos
- Indicador esticado: desenhar. Mão aberta: reposicionar/soltar. Punho fechado: apagar. Mindinho esticado, com os outros dedos recolhidos: selecionar e arrastar a forma ou traço sob o cursor.
- O contorno destaca o alvo; ao segurar, a seleção fica presa ao mesmo objeto. Cada mão pode mover um objeto diferente. Duas mãos não disputam o mesmo objeto.
- Formas fechadas aceitam seleção pelo interior; linhas e traços abertos, pela proximidade da linha. Seleciona o objeto de cima, respeitando a ordem do desenho. Um objeto corresponde a uma forma ou traço, sem segmentação semântica pela IA.
- Duplicar, Excluir, Desfazer e Refazer trabalham sobre a edição completa. Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y, Delete e Esc funcionam fora dos campos de texto. Esc cancela o arrasto. A ferramenta Mover objetos oferece a mesma operação pelo mouse.
- Os objetos permanecem dentro do quadro. A seleção é uma camada visual separada e não aparece na imagem exportada.
- Duas mãos com indicadores frente a frente (👉👈): segure um instante, depois afaste/aproxime para redimensionar o quadrado. Ele mantém os lados iguais. Solte para fixar. Círculo e retângulo continuam com os gestos anteriores.

## Música com som local
Abra o botão Música ou diga/digite “Jarvis abrir estúdio de música”. Clique em Ativar som; o primeiro carregamento lê cerca de 32 MB de amostras locais. Depois selecione o instrumento e, se quiser, Usar mãos.

Banco: 128 timbres General MIDI, mais bateria/percussão. Inclui pianos, órgãos, violões nylon/aço, guitarras, baixos, cordas, metais, flautas, sintetizadores, instrumentos étnicos e efeitos. Os nomes e programas vêm do banco GeneralUser GS 2.0.3; não significa reproduzir todo instrumento acústico existente.

- Cordas: passe o indicador pelas cordas. Escolha um acorde; guitarras/violões usam seis cordas e baixos usam quatro.
- Bateria: entre na área de cada peça com o indicador para bater; saia e entre novamente para repetir. Duas mãos independentes.
- Demais timbres: tocam no teclado de notas. Pode escolher também o visual de cordas.
- Mão aberta reposiciona sem tocar. Mouse e teclas A S D F G H J K L também tocam.
- Volume é separado do Jarvis. Parar som corta as notas. Fechar o estúdio ou suspender o Jarvis para o áudio; o motor fica suspenso fora do estúdio.
- Não usa API, conexão externa ou cota de IA para tocar. O processamento de áudio fica no AudioWorklet; o banco só carrega ao ativar som. A latência física inclui o intervalo de quadros da webcam.

Fontes e licenças, incluídas em assets/reactor_lab/music-bank:
- GeneralUser GS / S. Christian Collins: https://github.com/mrbumpy409/GeneralUser-GS
- SpessaSynth lib 4.3.14 / core 4.3.22, Apache-2.0: https://github.com/spessasus/spessasynth_lib
- stb-vorbis 0.0.6, licença original incluída.

## Libras: menos espera
- Alfabeto: 1,4 segundo / 7 quadros; sinais: 2,4 segundos / 10 quadros; frase: 4 segundos / 16 quadros.
- Mantém quadros ordenados com início e fim do movimento, JPEG 480×360. A interpretação continua experimental e precisa de revisão.
- Cliente HTTPS reutilizado; uma tentativa de API com timeout de 18 segundos. Não acumula as repetições automáticas do SDK quando a API falha.
- Captura contínua mantém intervalo mínimo de aproximadamente 8 segundos entre os pedidos, descontando o tempo de captura, sem pedidos simultâneos. Clique manual pode iniciar após a requisição atual terminar, com proteção de 2 segundos no backend.
- A UI separa a captura da espera do Gemini e mostra o tempo da resposta. Isso reduz esperas locais; não garante o tempo do servidor nem a precisão dos sinais.

Modelo padrão de Libras: Gemini 3.1 Flash-Lite, separado da configuração de imagens. Em 10/09, um teste de 7 quadros artificiais levou 5,7 s no 3.1; o pedido anterior no 3.5 excedeu o timeout (20,46 s medidos incluindo inicialização). Não é teste de precisão nem garantia de latência em sinais reais. Mantida a variável JARVIS_LIBRAS_MODEL para escolha explícita. Camada gratuita documentada: https://ai.google.dev/gemini-api/docs/pricing?hl=pt-br
