# Organizacao da pasta MARK-XL

A raiz foi deixada como area de entrada do Jarvis:

- `main.py`: launcher fino. Ele entra em `./arquivos` e executa o app real.
- `INICIAR_JARVIS_AUTOATUALIZAVEL.bat`: atalho para iniciar com o Python embutido e watcher.
- `.gitignore` e `.git`: arquivos de controle do repositorio.
- `arquivos/`: todo o codigo, configs, memoria, assets, logs e ferramentas do Jarvis.

Dentro de `arquivos/`:

- `main.py`: app principal original.
- `ui.py`: interface.
- `actions/`, `agent/`, `core/`: codigo do Jarvis.
- `config/`: configuracoes locais e credenciais. Nao commitar segredos.
- `memory/`: memoria local e mapas do Jarvis.
- `assets/`: imagens, screenshots e audio.
- `logs/boot/`: logs de inicializacao antigos.
- `Python/`: runtime Python embutido.
- `tools/`: ferramentas auxiliares.
- `docs/`: documentacao.

Comandos principais:

```powershell
# Rodar pelo launcher da raiz
C:\Users\Sabrina\Desktop\MARK-XL\arquivos\Python\bin\python.exe C:\Users\Sabrina\Desktop\MARK-XL\main.py

# Rodar com watcher autoatualizavel
C:\Users\Sabrina\Desktop\MARK-XL\INICIAR_JARVIS_AUTOATUALIZAVEL.bat
```

Se criar arquivos novos, regra simples: entrypoint na raiz so quando for para abrir o Jarvis; o resto vai em `arquivos/`.
