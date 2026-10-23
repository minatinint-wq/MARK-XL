# JARVIS Studio — anúncios animados sem GPU

Abra `tools\video\ABRIR_EDITOR_PROPAGANDA.bat`, ou diga ao Jarvis "abrir editor de propaganda" depois de reiniciá-lo.

## Uso

1. Clique em **Usar última imagem gerada**, **Imagens geradas pelo Jarvis** ou arraste mídias para a janela.
2. Escolha formato: 9:16 para anúncio vertical, 16:9 horizontal ou 1:1 quadrado.
3. Monte a sequência: mídia, duração, movimento, fade, texto da oferta, posição e tamanho da fonte. É possível duplicar, remover e reordenar cenas.
4. Opcionalmente use o roteiro por linhas `5s | zoom_in | Conheça nossa oferta`. Os movimentos aceitos são zoom_in, zoom_out, pan_left, pan_right, pan_up, pan_down e static. No editor, esse campo tem formato definido; o chat do Jarvis pode traduzir uma descrição livre para o roteiro estruturado.
5. Adicione uma trilha, se desejar. Ela será repetida/cortada para acompanhar o vídeo. O áudio original dos clipes não é mantido.
6. Gere uma prévia 480p, confira os textos e exporte MP4. A aba **Vídeo renderizado** permite assistir; **Abrir MP4** usa o reprodutor do Windows.
7. Salve o projeto JSON para reabrir e editar depois. Mantenha os arquivos de mídia nas mesmas pastas.

Saídas: `generated_videos/cpu/`. Cada exportação recebe um nome novo. O vídeo é H.264 com áudio AAC quando há trilha. A prévia da imagem original não simula os efeitos; a prévia renderizada mostra o resultado.

## Desempenho

Python e FFmpeg trabalham sem GPU. A codificação usa libx264, preset veryfast, CRF 23, até quatro threads e cenas processadas uma a uma. Padrão: 720p/24 fps; use 480p/15 fps em máquinas mais lentas. Não carregamos quadros inteiros em listas Python nem instalamos modelos de IA.

O PC precisa ficar ligado durante a renderização. Jobs iniciados pelo chat param ao encerrar/reiniciar o Jarvis; o editor roda num processo separado. Temporários são removidos ao concluir/cancelar normalmente. Limites: 20 mídias, 20 cenas, 60 segundos por cena, 180 segundos totais. Vídeos curtos são repetidos até completar a duração da cena. Fades passam por preto; não são dissolvências sobrepostas. O enquadramento preserva proporção com barras quando necessário.

A animação aplica movimento de câmera, cor, texto e montagem em imagens existentes. Não cria movimentos novos de personagens/produtos, animação 3D, sincronização labial ou recorte automático em camadas.

## Instalação simples

Neste PC, Python, PyQt6 e FFmpeg já estavam disponíveis. Nenhum modelo foi baixado. Em outra instalação do MARK-XL, execute `tools\video\INSTALAR_ANIMACAO_CPU.bat`: ele verifica o Python embutido e instala somente PyQt6 e/ou imageio-ffmpeg se faltarem. O módulo de renderização também pode usar qualquer Python 3.11+ e FFmpeg no PATH. No Linux, textos exigem `ANIMATION_FONT` apontando para um TTF. `FFMPEG_BINARY` pode apontar para um FFmpeg alternativo.

## Chat e script Python

A ferramenta `video_generation` aceita provider `ffmpeg` e ações:
- `cpu_editor`: abre o editor; `project_path` é opcional.
- `cpu_start`: inicia a conversa, solicitando estilo, arquivos e roteiro que faltarem.
- `cpu_media` / `cpu_plan`: acrescentam arquivos e roteiro ao rascunho da sessão.
- `cpu_render`: renderiza em segundo plano e retorna o identificador.
- `cpu_status` / `cpu_cancel`: consultam/cancelam o trabalho, com `job_id` opcional.
- `cpu_check`: verifica FFmpeg.

Estilos: cinematic, suave, dinamico, documental, vintage. `media_paths` é uma lista de caminhos. `animation_script` é JSON com `scenes`, `size`, `fps`, `ratio` e `audio_path` opcional. Cenas usam `media` a partir de 1, `duration`, `motion`, `fade`, `caption`, `caption_position` e `caption_size`. Somente chat/CLI aceitam também `start` para o início do trecho de vídeo. O editor recusa projetos com esse deslocamento para não perder a informação.

Terminal: `Python\pythoncore-3.14-64\python.exe -m actions.animation_cpu`.
Arquivo: `Python\pythoncore-3.14-64\python.exe -m actions.animation_cpu --plan projeto.json`.

## Validação

`Python\pythoncore-3.14-64\python.exe -m tools.test_animation_cpu`

Foram testados: entrada progressiva por chat, roteiro inválido, sete movimentos, MP4 real/contagem de quadros, proporção vertical, texto com acentos e símbolos, trilha AAC, proteção contra sobrescrita, cancelamento, interface Qt, projetos, sequência e roteamento da ferramenta. O teste usa mídias sintéticas em `generated_videos/cpu/verification`. A conversa real de voz depende do Gemini e não faz parte deste teste.

## Referências consultadas

Implementação original; nenhuma cópia de código desses projetos foi incorporada.
- https://github.com/aorthey/video_manipulation — composição de clipes, imagens, textos e áudio.
- https://github.com/coderefinery/ffmpeg-editlist — edição declarativa por cenas/trechos.
- https://github.com/0xnyn/vibestudio — operações FFmpeg acessíveis a ferramentas/agentes.
- https://ffmpeg.org/ffmpeg-filters.html — filtros; disponibilidade conferida também no FFmpeg local.
- https://github.com/imageio/imageio-ffmpeg — instalação opcional com binário FFmpeg.
