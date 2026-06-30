# Lista de Funções do MARK-XL

Este é o índice público de funções do MARK-XL. Algumas funções exigem configuração local, chaves de API, dispositivos pareados, apps instalados ou vault Obsidian configurado.

## Runtime Principal

| Função | Módulo | Observações |
|---|---|---|
| Runtime de voz | `main.py` | Sessão em tempo real e execução de ferramentas |
| UI/HUD | `ui.py` | Interface desktop e estados visuais |
| Roteamento por prompt | `core/prompt.txt` | Regras de comportamento e seleção de ferramentas |
| Planner/executor | `agent/` | Planejamento e execução de tarefas multi-etapa |

## Voz e Áudio

| Função | Módulo | Observações |
|---|---|---|
| Fallback de áudio | `actions/audio_fallback.py` | Suporte reserva para fala/áudio |
| Aprendizado de sons | `actions/sound_learning.py` | Aprende e classifica sons do ambiente |
| Modo bilíngue | `actions/bilingual_mode.py` | Tradução e suporte de idioma |
| Mute temporário | `main.py` | Fica quieto até ouvir a wake word |
| Métricas de voz | `main.py` / UI | Visualização do sintetizador do usuário |

## Visão

| Função | Módulo | Observações |
|---|---|---|
| Processamento de tela | `actions/screen_processor.py` | Analisa a tela atual |
| Live vision | `actions/live_vision.py` | Contexto visual contínuo |
| Contexto do desktop | `actions/vision_desktop_context.py` | Captura tela/janela ativa |
| Aprendizado visual | `actions/vision_learning.py` | Preferências e eventos visuais |
| UI de mão/câmera | `actions/camera_hand_ui.py` | Interface com tracking da mão |
| Braille por dedos | `actions/hand_braille.py` | Suporte a gestos/braille |
| Reconhecimento facial | `actions/face_recognition.py` | Dados locais; manter privado |

## Cérebro e Memória Obsidian

| Função | Módulo | Observações |
|---|---|---|
| Gerenciador de memória | `memory/memory_manager.py` | Busca, índice e grupos do vault |
| Brain mode | `actions/brain_mode.py` | Pesquisa, sono, pin e módulos |
| Modo estudo | `actions/study_mode.py` | Ciclos de aprendizado em notas |
| Controle Obsidian | `actions/obsidian_controller.py` | Ler, criar, mover, taguear e abrir notas |
| Memória operacional | `actions/operation_memory.py` | Aprende preferências operacionais |
| Mapa neural | `memory_map.html` | Visualização local do conhecimento |
| Ferramentas do vault | `tools/` | Organização e compactação |

## Desktop e Automação

| Função | Módulo | Observações |
|---|---|---|
| Abrir apps | `actions/open_app.py` | Abre apps e jogos instalados |
| Controle do PC | `actions/computer_control.py` | Mouse, teclado, clipboard e janelas |
| Configurações do PC | `actions/computer_settings.py` | Ações e ajustes do sistema |
| Controle desktop | `actions/desktop.py` | Tarefas no desktop |
| Comandos rápidos | `actions/quick_commands.py` | Comandos padrão salvos |
| Macros de automação | `actions/automation.py` | Fluxos reutilizáveis multi-etapa |
| Lembretes/alarmes | `actions/reminder.py` | Alarmes e lembretes no PC |
| Arquivos | `actions/file_controller.py` | Operações genéricas em arquivos/pastas |
| Processador de arquivos | `actions/file_processor.py` | Análise/processamento de arquivos |

## Mapas e Clima

| Função | Módulo | Observações |
|---|---|---|
| Modo maps | `actions/maps_mode.py` | Endereço, CEP, rota e tempo estimado |
| Previsão do tempo | `actions/weather_report.py` | Clima atual, chuva e previsão por cidade/CEP/coordenadas |

## Web, Busca e Mídia

| Função | Módulo | Observações |
|---|---|---|
| Busca web | `actions/web_search.py` | Busca e comparação |
| Controle navegador | `actions/browser_control.py` | Automação do browser |
| Busca de imagem/vídeo | `actions/image_search.py` | Busca/download por provedores configurados |
| YouTube | `actions/youtube_video.py` | Play, resumo e tendências |
| Info service | `actions/info_service.py` | Notícias, mercado e consultas gerais |
| Wallpaper Engine | `actions/wallpaper_engine.py` | Controle local do Wallpaper Engine |

## Jogos e Steam

| Função | Módulo | Observações |
|---|---|---|
| Atualizador de jogos | `actions/game_updater.py` | Instalar, atualizar e listar downloads |
| Controle de jogos | `actions/game_control.py` | Input limitado no jogo ativo |
| Visão de jogos | `actions/game_vision.py` | Analisa a tela do jogo |
| Steam Store | `actions/steam_store.py` | Preços, loja e Task Bar Hero |

## Celular, Social e Smart Home

| Função | Módulo | Observações |
|---|---|---|
| Ponte iPhone | `actions/iphone_bridge.py` | Phone Link, Bluetooth e URI handlers |
| Atalhos iPhone | `actions/iphone_shortcuts.py` | Eventos locais dos Atalhos |
| Controle social | `actions/social_control.py` | WhatsApp/Instagram web/app |
| Smart home | `actions/smart_home.py` | Smart home e ponte Spotify |
| Spotify | `actions/spotify_control.py` | Reprodução, dispositivos e conta |

## Código e Dev Tools

| Função | Módulo | Observações |
|---|---|---|
| Code helper | `actions/code_helper.py` | Ajuda em código |
| Dev agent | `actions/dev_agent.py` | Suporte a tarefas de desenvolvimento |
| LLM local | `actions/local_llm.py` | Ollama, presets e respostas locais |

## Arquivos Locais Que Não Devem Ir Para o GitHub

- `config/api_keys.json`
- `config/*credentials*.json`
- `memory/*.json`
- `memory/sound_samples/`
- dados faciais, screenshots, exports pessoais do Obsidian e índices gerados