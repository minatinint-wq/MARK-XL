# MARK-XL

**Sistema pessoal de IA local-first para comando e automação no Windows.**

O MARK-XL é um assistente estilo Jarvis feito para voz, visão, memória local, automação do desktop, Obsidian, mídia, mapas, clima, jogos e fluxos pessoais. Ele roda no PC do usuário, usa um cérebro local para manter contexto e executa comandos práticos em vez de apenas conversar.

> Status: build pessoal ativo. Alguns módulos dependem de apps locais, chaves de API, pareamento de dispositivos ou permissões do Windows.

---

## Identidade

| Item | Valor |
|---|---|
| Nome | MARK-XL |
| Persona | JARVIS / IA operacional local |
| Foco | Automação do PC, memória local, visão, voz, pesquisa e fluxos pessoais |
| Plataforma principal | Windows |
| Base de conhecimento | Vault Obsidian + índices JSON locais |
| Estilo de uso | Voz primeiro, ações por ferramentas, local-first quando possível |

---

## Funções Principais

### Voz e Conversa

- Conversa por voz em tempo real pela interface principal do JARVIS.
- Mute temporário: diga `muta` e ele fica quieto até ouvir `JARVIS` novamente.
- Sintetizador/visualizador da voz do usuário para monitorar frequências.
- Controle de buffer de áudio para reduzir sobreposição de falas.
- Modo de aprendizado de sons para gravar e reconhecer barulhos recorrentes.

### Visão e Câmera

- Visão de tela para analisar o que está no PC.
- Modo live vision para contexto visual contínuo.
- UI de mão/câmera com overlays tecnológicos.
- Modo braille por gestos dos dedos.
- Modo desenho com interação por dedos.
- Visão de jogos para analisar telas de gameplay.

### Cérebro Obsidian

- Leitura e busca no vault Obsidian em `D:\xxxx_memory`.
- Mapa neural em HTML para visualizar grupos de conhecimento.
- Modo cérebro com pesquisa, sono e consolidação.
- Modo estudo com ciclos contínuos de aprendizado.
- Índice de busca otimizado para vaults grandes.
- Controle Obsidian para criar, ler, mover, taguear e organizar notas.

### IA Local

- Controlador local via Ollama com presets rápido/profundo.
- Preset rápido alvo: `llama3.2:1b`.
- Preset profundo alvo: `llama3.1:8b`.
- Respostas locais com contexto do Obsidian quando configurado.
- Gemini continua como camada de voz, visão e fallback.

### Automação do Desktop

- Abrir apps e jogos.
- Controle de teclado e mouse.
- Ler, copiar e colar conteúdo da área de transferência.
- Foco, minimizar, maximizar, fechar e organizar janelas.
- Comandos rápidos e macros reutilizáveis.
- Alarmes e lembretes no PC.
- Operações com arquivos e pastas com limites de segurança.

### Mapas e Clima

- Modo maps para endereços, ruas, CEP e links do Google Maps.
- Estimativa de rota: `quantos minutos de X ate Y`.
- Distância e link da rota.
- Previsão do tempo por cidade, endereço, CEP ou coordenadas.
- Clima atual, hoje/amanhã, chance de chuva, temperatura, vento e umidade.

### Mídia e Web

- Automação do navegador via Chrome/Playwright.
- Busca web.
- Busca e download de imagens/vídeos por APIs configuradas.
- Helper para YouTube.
- Controle do Wallpaper Engine.
- Controle Spotify e smart home quando conta/dispositivo permitirem.

### Jogos

- Atualização/instalação/status de jogos estilo Steam/Epic.
- Perfis de controle para ações limitadas de teclado/mouse.
- Consulta de preços na Steam Store, incluindo Task Bar Hero.
- Visão de jogos para análise da tela ativa.

### Celular e Social

- Ponte iPhone via Bluetooth, Phone Link, URI handlers e atalhos locais.
- Bridge para Atalhos do iPhone com eventos de bateria, localização, clipboard, foto/áudio e foco.
- Helpers para WhatsApp/Instagram web/app, abrindo chats/perfis e enviando mensagens explícitas do usuário.
- Não existe controle silencioso total do iOS: confirmações e limites da Apple continuam valendo.

---

## Estrutura do Repositório

| Caminho | Função |
|---|---|
| `main.py` | Runtime principal e registro de ferramentas |
| `ui.py` | Interface/HUD desktop |
| `actions/` | Módulos de automação, visão, mídia, mapas, clima, jogos etc. |
| `agent/` | Planner/executor para tarefas multi-etapa |
| `core/prompt.txt` | Prompt principal de roteamento e comportamento |
| `memory/` | Memória local e índices gerados; dados pessoais devem ficar privados |
| `config/` | Configuração local; chaves reais nunca devem ser commitadas |
| `tools/` | Scripts de manutenção e organização do Obsidian |
| `docs/` | Documentação pública, branding e lista de funções |

---

## Início Rápido

```bash
pip install -r requirements.txt
playwright install
python main.py
```

Serviços locais opcionais:

```bash
ollama serve
ollama pull llama3.2:1b
ollama pull llama3.1:8b
```

---

## Segurança

- Mantenha segredos reais em arquivos locais ignorados pelo Git.
- Não publique dumps de memória, exports do vault Obsidian, dados faciais, amostras de som ou índices privados.
- Algumas automações controlam teclado/mouse. Use comandos limitados e evite fluxos destrutivos sem supervisão.

---

## Branding

Veja [BRANDING.pt-BR.md](BRANDING.pt-BR.md).

## Índice de Funções

Veja [FUNCTIONS.pt-BR.md](FUNCTIONS.pt-BR.md).