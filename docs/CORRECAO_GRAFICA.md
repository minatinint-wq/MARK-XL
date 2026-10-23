# Renderização e desempenho — 10/09/2026

O padrão atual é hardware: Qt e ANGLE usam a GPU Intel via Direct3D 11. O WARP deixou de ser padrão porque sobrecarregou a CPU do notebook. A armadura continua metálica, com antialiasing e controle interativo.

## Medição local

Comparação de três execuções isoladas da interface, sem Gemini Live, câmera ou voz, na mesma máquina. Cada execução mediu aproximadamente 12 segundos após o 3D ficar pronto; os valores somam o processo do Jarvis e seus filhos, normalizados pelo total de CPUs lógicas.

| Configuração | CPU média | Pico |
| --- | ---: | ---: |
| WARP anterior | 79.8% | 87.8% |
| GPU antes de otimizar | 15.9% | 40.5% |
| GPU com as otimizações | 13.7% | 35.3% |

Esses números são do Jarvis nesse cenário de teste. O indicador CPU da interface mostra o total do computador e pode incluir outros aplicativos, câmera, áudio e picos da inicialização.

## Comportamento atual

- GPU: até 30 quadros/s durante fala ou interação; até 15 em repouso.
- Com música, Libras ou sketchbook aberto, o 3D mantém a última imagem e pausa seus desenhos. O painel, a câmera e o áudio continuam funcionando.
- Suspenso: a armadura apagada e o reator vermelho são desenhados uma vez, com nova pintura somente se houver redimensionamento ou retomada.
- Resolução máxima do 3D: 900 mil pixels, com antialiasing mantido.
- A captura de câmera DirectShow continua configurada.
- Se WebGL selecionar software apesar do perfil solicitado, o 3D detecta isso e usa um orçamento menor: 12 quadros/s em atividade, 4 em repouso, 350 mil pixels.

JARVIS_GRAPHICS_MODE=compat continua disponível apenas como fallback manual para diagnóstico. JARVIS_GRAPHICS_MODE=auto mantém a escolha padrão do Qt. O padrão recomendado no código agora é hardware.

## Histórico e limite da correção

O evento Windows Application Error 1000 de 10/09/2026 às 00:45:41 registrou 0xc0000005 em igd10iumd64.dll, versão Intel 30.0.100.9805. O perfil WARP havia sido usado para contornar o driver, mas seu custo de CPU foi inadequado. Esta mudança recupera a aceleração e reduz trabalho desnecessário; ela não atualiza o driver nem comprova a eliminação definitiva daquela falha nativa. O diagnóstico local continua em logs/native_crash.log.

Referências técnicas: [Qt / renderização no Windows](https://doc.qt.io/qt-6.8/windows-graphics.html), [Qt WebEngine / backends](https://doc.qt.io/qt-6/qtwebengine-features.html).
