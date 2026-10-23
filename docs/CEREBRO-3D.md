# Cérebro de memória 3D

Abra `memory_brain_3d.html` diretamente no navegador. Funciona offline com os arquivos em `assets/brain_3d` e o índice existente em `memory/neural_map_data.js`.

- Cada entrada de nota do índice corresponde a um único ponto, sem hubs contados como notas. A posição é determinística e forma dois hemisférios com dobras e fissura central. O layout é uma representação visual, não uma localização anatômica ou o funcionamento interno de um modelo de IA.
- Caminhos representam relações de pasta, grupo e tags presentes nos metadados. Não são hyperlinks extraídos do conteúdo nem inferências semânticas. A consulta de rota percorre essas relações com busca em largura. Não inventa conexões quando não existe caminho.
- Arraste para girar, use a roda para aproximar, clique numa nota para ver os caminhos dela. A busca encontra títulos, pastas, grupos e tags. A nota pode ser aberta no arquivo local ou ter seu caminho copiado.
- Atalhos: / para buscar, 0 para centralizar, Esc para limpar e centralizar, R para a rota selecionada. Os controles superiores centralizam, mostram de cima e ativam giro automático.
- Caminhos podem ser ocultos ou ter intensidade ajustada. Fluxo vivo controla a animação contínua. Sem pulso, giro, rota ou interação, não são redesenhados quadros. Ao esconder a aba, a renderização para.
- Limites: 12 FPS em repouso e 24 FPS interativo, até 900 mil pixels no framebuffer. Renderizador por software usa 4/12 FPS e 450 mil pixels. Não há pós-processamento, sombras, câmera, microfone ou chamadas de IA neste HTML.
- A visualização usa Three.js r170 e OrbitControls já presentes no Jarvis, empacotados como scripts clássicos para compatibilidade com file://. A licença MIT está em `assets/brain_3d/THREE-LICENSE.txt`.
- Não altera os arquivos de memória nem o renderizador da armadura. O índice continua sendo atualizado pelo fluxo já existente do Jarvis.

Validação em 10/09/2026: 16.119 notas/pontos, 25 grupos e 32.296 relações no índice testado. Integridade de todas as relações verificada; 20 verificações de interface aprovadas, incluindo seleção por cursor, filtros, rotas, pausa, links locais e uso estável de geometrias. Zero requisições externas e zero erros JS no teste QtWebEngine/Intel Iris Xe. CPU média do processo de teste e seus filhos normalizada pelo computador: 5,74%, pico 9,06% no cenário exercitado; não é medição do Jarvis completo.


## Acesso dentro do Jarvis

A partir de 11/09/2026, o painel principal tem o botão CÉREBRO 3D ao lado de NEURAL MAP. Atalho: Ctrl+F3. O botão CÉREBRO 3D do Nexus Lab (F2) continua disponível.

Comando por voz ou texto: "Jarvis, abre o cérebro 3D". O reconhecimento do comando usa a transcrição que o Jarvis já recebe e abre a janela interna por um sinal Qt; não faz uma segunda consulta de intenção para esta frase. Por texto, também funciona durante reconexão. A voz respeita suspensão e privacidade.

Todos os acessos carregam o mesmo memory_brain_3d.html da pasta MARK-XLIV, sem reconstruí-lo. Chamadas repetidas reutilizam a janela e o fechamento destrói a visualização para liberar recursos. A ferramenta computer_settings, action=open_brain_3d (e aliases), usa a UI quando anexada; fora do Jarvis conserva a abertura no navegador.

Validação: 25 verificações aprovadas, incluindo arquivo correto embutido, botão, atalho registrado, comando reconhecido, chamadas por outra thread, reutilização, descarte ao fechar e nova abertura. Não foram feitas chamadas às APIs de voz durante os testes.


## Cores de classe e ativação (versão anterior)

Em 11/09/2026, as oito cores repetidas foram substituídas por uma paleta de classes distintas: os 25 grupos atuais têm cores exclusivas, compartilhadas pelos pontos, legenda, título do grupo selecionado e conexões selecionadas.

Ao abrir o cérebro, pequenos pulsos percorrem arestas existentes durante cerca de 3,6 segundos, com uma onda suave de iluminação. São indicadores de ativação visual, sem criar notas ou alegar atividade real de IA. Um único objeto gráfico pré-alocado gera os pulsos: limite de 480 partículas (456 no índice testado), uma chamada de desenho adicional somente durante a ativação. Há um limite menor em renderização por software. Filtros, seleção e rotas encerram a ativação para não misturar os destaques. Desmarcar Pulsar também interrompe o efeito; a preferência do sistema por movimento reduzido impede seu início. A renderização continua pausando em abas ocultas.

Validação: 32 verificações de UI aprovadas, incluindo cores únicas, início/fim, não acumular ativações, estabilidade de geometrias e recursos existentes; 4 verificações adicionais de movimento reduzido aprovadas. Zero erros JS ou requisições externas. CPU média do processo de teste e filhos normalizada pelo computador: 5,11%, pico 12,86% nesse cenário; não corresponde ao Jarvis completo. HTML e índice de notas mantidos no mesmo local.


## Fluxo vivo contínuo — versão atual

Em 11/09/2026, a onda de ativação e os pulsos em rajada foram substituídos por até seis luzes pequenas que caminham continuamente por conexões existentes. Cada luz tem apenas duas amostras curtas de rastro: até 18 partículas em um único objeto gráfico, ou 9 em renderização por software. O número não cresce com o tempo.

A entrada é gradual, sem clarão; o movimento entre notas é lento e suavizado, com durações variadas. O brilho geral varia somente 1,5%, em aproximadamente 11 segundos. As 25 cores de classe são preservadas.

O controle Fluxo vivo pausa ou retoma o movimento. Desativar Caminhos também oculta as luzes. Filtros restringem o movimento às relações visíveis; seleção e rotas deixam o fluxo mais discreto. Aba oculta ou visualização pausada não redesenha quadros. A preferência de movimento reduzido começa com o fluxo desativado.

A animação usa os limites de quadros existentes: 12 FPS em repouso, 24 durante interação; software 4/12 FPS. O avanço das luzes considera o tempo entre quadros e retoma sem salto após pausa. Há apenas uma chamada de desenho adicional para todas as luzes, sem pós-processamento.

Validação: 36 verificações de interface aprovadas, incluindo continuidade, mudança de notas, limite fixo de partículas, pausa/retomada, filtros, seleção e rotas; quatro verificações de movimento reduzido aprovadas. Zero erros JS e zero requisições externas no teste final. CPU média do processo de teste e filhos normalizada pelo computador: 5,51%, pico 10,94% no cenário; não corresponde ao Jarvis completo.


### Visibilidade do fluxo

Em 11/09/2026, as seis luzes ganharam um núcleo claro e halo na cor da classe, com rastros mais legíveis sobre o cérebro denso. O destaque é calculado no próprio sprite; não acrescenta objetos, partículas, pós-processamento nem chamadas de desenho. Foram preservados o modelo, a luminosidade geral, as cores das classes, a velocidade lenta e a entrada gradual. A seleção ainda reduz o brilho do fluxo, sem escondê-lo.

O progresso de câmera e rota também passa a respeitar o limite inferior zero: um quadro já agendado pode ter timestamp anterior ao início da rota. Isso evita interpolação com índice negativo e coordenadas inválidas no primeiro quadro.

Validação do destaque: 37 verificações da interface aprovadas; zero erros JS, geometrias inválidas ou requisições externas. Mantidos seis sinais, 18 partículas e três chamadas de desenho no estado inicial.


## Contagem de notas e maior atividade visual

Agora há até 18 sinapses contínuas, com dois pontos de rastro por sinal (54 partículas, seis sinais/18 partículas em software). Continuam na mesma chamada de desenho e preservam as pausas e os limites de quadros.

Frases como “Jarvis, quantas notas tem no Obsidian?” e “conte as notas do cérebro” fazem a contagem local em uma thread, sem consulta de intenção/RAG. O resultado usa o contador existente de arquivos de notas; não carrega seu conteúdo para contar. A resposta de voz continua pelo caminho existente. Transcrições repetidas em três segundos são ignoradas.

O início da consulta abre o cérebro na UI e ativa um pulso de leitura sobre pontos e caminhos. Status/stats do Obsidian e do brain mode também emitem o evento. O fim é emitido inclusive se houver erro. O efeito permanece por no mínimo 3,2 segundos, sem atrasar a resposta, e depois retorna ao fluxo contínuo. Fluxo vivo desativado e movimento reduzido impedem o pulso; a mensagem de consulta continua disponível.

A UI recebe os eventos por sinal Qt. O HTML na mesma URL file:// recebe um pequeno arquivo local de atividade a cada dois segundos, apenas enquanto visível. Esse arquivo contém somente tipo, fase e horários, sem conteúdo, nomes ou caminhos de notas. Atualização atômica, revisões ordenadas e limite de dois minutos impedem estado parcial, eventos antigos e pulso permanente após encerramento abrupto. O índice de notas não é recarregado durante o efeito.

Validação: 94 verificações aprovadas entre parser/contagem com notas fictícias, eventos de sucesso e erro, concorrência, UI Qt, leitura no arquivo file://, renderização, pausas e movimento reduzido. Zero erros JS, geometrias inválidas ou chamadas externas na verificação geral. Não houve chamadas às APIs de voz nem leitura de conteúdo de notas reais.
