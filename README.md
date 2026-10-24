# MARK-XLIV

[English](README.md) | [Português (Brasil)](docs/README.pt-BR.md)


**Local-first personal AI command system for Windows.**

MARK-XLIV is a Jarvis-style assistant built around voice, vision, local memory, desktop automation, Obsidian knowledge, media tools, maps, weather, games, and personal workflows. It is designed to run on the user's PC, remember context through a local brain, and execute practical commands instead of only chatting.

> Status: active personal build. Some modules depend on local apps, API keys, device pairing, or Windows permissions.

---

## Core Identity

| Item | Value |
|---|---|
| Name | MARK-XLIV |
| Assistant persona | JARVIS / local operational AI |
| Focus | PC automation, local memory, vision, voice, research, and personal workflows |
| Primary platform | Windows |
| Knowledge base | Obsidian vault + local JSON indices |
| Runtime style | Voice-first, tool-driven, local-first when possible |

---

## Main Functions

### Voice and Conversation

- Real-time voice conversation through the main JARVIS interface.
- Temporary wake mute: say `muta` and it stays quiet until it hears `JARVIS` again.
- User voice synthesizer/visualizer support for frequency monitoring.
- Audio buffer controls to reduce overlapping speech.
- Sound learning mode for recording and identifying recurring sounds.

### Vision and Camera

- Screen vision for analyzing the current PC screen.
- Live vision mode for continuous visual context.
- Camera hand UI with visual tracking overlays.
- Braille hand mode for detecting finger/sign patterns.
- Drawing mode for finger-guided interaction.
- Game vision mode for watching active game screens.

### Obsidian Brain

- Reads and searches the Obsidian vault at `D:\xxxx_memory`.
- Neural map HTML for visualizing knowledge groups.
- Brain mode with sleep/consolidation workflows.
- Study mode with repeated learning cycles.
- Optimized vault search index for large note counts.
- Obsidian controller for creating, reading, moving, tagging, and organizing notes.

### Local AI

- Local Ollama controller with Normal, Fast, and Ultra on-demand presets.
- Normal: `llama3.2:1b`, low effort, 2K context, thinking off.
- Fast: `qwen3.5:4b`, medium effort, 4K context, thinking on.
- Ultra: `gemma4:latest` (8B), high effort, 8K context, thinking on.
- The main console includes three clickable model cards with live loading, thinking, response, and RAM-release states plus a compact thinking monitor.
- Research results are summarized locally before returning to Gemini Live, and models unload after each request.
- Gemini remains available for voice, vision, and fallback workflows.

### Desktop Automation

- Open apps and games.
- Keyboard and mouse control.
- Clipboard read/copy/paste helpers.
- Window focus, minimize, maximize, close, and arrange.
- Quick commands and reusable automation macros.
- PC reminders and alarms.
- File and folder operations with safety boundaries.

### Maps and Weather

- Maps mode for addresses, streets, CEP lookup, and Google Maps links.
- Route time estimates: `quantos minutos de X ate Y`.
- Distance estimates and route links.
- Weather forecast by city, address, CEP, or coordinates.
- Current weather, today/tomorrow forecast, rain chance, temperature, wind, and humidity.

### Media and Web

- Browser automation through Chrome/Playwright flows.
- Web search tool.
- Image and video search/download through provider APIs where configured.
- YouTube helper.
- Wallpaper Engine control.
- Spotify control and smart-home bridge where account/device state allows.

### Games

- Game updater for Steam/Epic style install/update/status workflows.
- Game control profiles for bounded keyboard/mouse actions.
- Steam Store price lookup, including Task Bar Hero helpers.
- Game vision for active gameplay analysis.

### Phone and Social

- iPhone bridge through Windows Bluetooth, Phone Link, URI handlers, and local shortcut workflows.
- iPhone Shortcuts local bridge for events such as battery, location, clipboard, photo/audio, and focus state.
- WhatsApp/Instagram web/app helpers for opening chats/profiles and sending explicit user-requested messages.
- No silent full iOS remote control: iOS confirmation and app limitations still apply.

---

## Repository Layout

| Path | Purpose |
|---|---|
| `main.py` | Main JARVIS runtime and tool registration |
| `ui.py` | Desktop interface/HUD |
| `memory_brain_3d.html` | Local 3D knowledge visualization (build your own private index) |
| `assets/reactor_lab/` | 3D armor, hand tracking and music-studio interface |
| `assets/brain_3d/` | Offline brain renderer |
| `actions/` | Tool modules for automation, vision, media, maps, weather, games, etc. |
| `agent/` | Planner/executor support |
| `core/prompt.txt` | Main routing/personality/tool-use prompt |
| `memory/` | Local runtime memory and generated indices; most personal/generated files should stay private |
| `config/` | Local configuration; real API keys should never be committed |
| `tools/` | Maintenance and Obsidian organization scripts |
| `docs/` | Public documentation, branding, and function lists |

---

## Quick Start

```bash
pip install -r requirements.txt
playwright install
python main.py
```

On Windows, `INICIAR_JARVIS_AUTOATUALIZAVEL.bat` uses the bundled Python,
`.venv`, or the installed `py -3` launcher. Optional 3D and Fish voice
dependencies are listed separately in `requirements-reactor-3d.txt` and
`requirements-fish-voice.txt`. The 3D brain needs a locally built index; no
personal notes or generated index are included in this repository.

On PCs with 10 GiB of RAM or less, JARVIS automatically uses the lighter Qt
canvas instead of starting the Chromium/WebGL armor. Set
`MARK_XL_LOW_MEMORY=1` to force this mode, or `MARK_XL_LOW_MEMORY=0` to keep
the 3D armor. For an 8 GB PC, select the Normal local model and avoid loading
multiple local models at once. The startup briefing sends one voice request;
if the service is slow, it logs the timeout without restarting the report.

For the voice-glow-only 8 GB edition, launch `INICIAR_JARVIS_8GB.bat`.
See [the Portuguese transfer guide](docs/EDICAO_8GB.md). Credentials are
transferred separately in a private local folder, never committed here.

Local optional services:

```bash
ollama serve
ollama pull llama3.2:1b
ollama pull qwen3.5:4b
ollama pull gemma4:latest
```

---

## Safety Notes

- Keep real secrets in ignored local config files.
- Do not commit personal memory dumps, Obsidian vault exports, face data, sound samples, or generated private indices.
- Some automation can control keyboard/mouse. Use bounded commands and avoid unattended destructive workflows.

---

## Branding

See [docs/BRANDING.md](docs/BRANDING.md) for naming, tone, visual direction, and repository presentation.

## Function Index

See [docs/FUNCTIONS.md](docs/FUNCTIONS.md) for the detailed function/module list.

---

## License

Personal/non-commercial use unless a separate license is added by the repository owner.
