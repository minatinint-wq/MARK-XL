# MARK-XL Function List

This is the public function index for the MARK-XL repository. Some functions require local setup, API keys, paired devices, installed apps, or a configured Obsidian vault.

## Core Runtime

| Function | Module | Notes |
|---|---|---|
| Main voice runtime | `main.py` | Real-time JARVIS session and tool execution |
| UI/HUD | `ui.py` | Desktop interface and state display |
| Prompt routing | `core/prompt.txt` | Tool selection and behavior rules |
| Planner/executor | `agent/` | Multi-step task planning and execution |

## Voice and Audio

| Function | Module | Notes |
|---|---|---|
| Audio fallback | `actions/audio_fallback.py` | Backup speech/audio handling |
| Sound learning | `actions/sound_learning.py` | Learn/classify recurring environment sounds |
| Bilingual mode | `actions/bilingual_mode.py` | Language/translation helper mode |
| Temporary mute | `main.py` | Wake-word mute gate |
| Voice metrics | `main.py` / UI | User synthesizer visual feedback |

## Vision

| Function | Module | Notes |
|---|---|---|
| Screen processing | `actions/screen_processor.py` | Analyze current PC screen |
| Live vision | `actions/live_vision.py` | Continuous screen/camera context |
| Desktop context capture | `actions/vision_desktop_context.py` | Window/screen context support |
| Vision learning | `actions/vision_learning.py` | Preferences/events for visual modules |
| Camera hand UI | `actions/camera_hand_ui.py` | Hand-tracking visual interface |
| Braille/finger detection | `actions/hand_braille.py` | Braille-oriented gesture support |
| Face recognition | `actions/face_recognition.py` | Local face data; keep private |

## Obsidian Brain and Memory

| Function | Module | Notes |
|---|---|---|
| Memory manager | `memory/memory_manager.py` | Vault search/index/group generation |
| Brain mode | `actions/brain_mode.py` | Pesquisa, sono, pin, modules |
| Study mode | `actions/study_mode.py` | Cyclic learning notes |
| Obsidian control | `actions/obsidian_controller.py` | Read/create/move/tag/open notes |
| Operation memory | `actions/operation_memory.py` | Learns operational preferences |
| Neural map | `memory_map.html` | Local visual knowledge map |
| Vault tools | `tools/` | Organization/compaction scripts |

## Desktop and Automation

| Function | Module | Notes |
|---|---|---|
| Open apps | `actions/open_app.py` | Launch installed apps/games |
| Computer control | `actions/computer_control.py` | Mouse, keyboard, clipboard, windows |
| Computer settings | `actions/computer_settings.py` | OS settings and system actions |
| Desktop control | `actions/desktop.py` | Desktop tasks |
| Quick commands | `actions/quick_commands.py` | Saved standard commands |
| Automation macros | `actions/automation.py` | Reusable multi-step workflows |
| Reminders/alarms | `actions/reminder.py` | PC reminders and alarms |
| File controller | `actions/file_controller.py` | Generic file/folder operations |
| File processor | `actions/file_processor.py` | File analysis/processing |

## Maps and Weather

| Function | Module | Notes |
|---|---|---|
| Maps mode | `actions/maps_mode.py` | Address, CEP, route, route time estimate |
| Weather forecast | `actions/weather_report.py` | Current weather, rain, forecast by city/CEP/coords |

## Web, Search, Media

| Function | Module | Notes |
|---|---|---|
| Web search | `actions/web_search.py` | Search/comparison helper |
| Browser control | `actions/browser_control.py` | Browser automation |
| Image/video search | `actions/image_search.py` | Provider-based media search/download |
| YouTube helper | `actions/youtube_video.py` | Play/summarize/trending helpers |
| Info service | `actions/info_service.py` | Market/news/info style queries |
| Wallpaper Engine | `actions/wallpaper_engine.py` | Wallpaper control via local executable |

## Games and Steam

| Function | Module | Notes |
|---|---|---|
| Game updater | `actions/game_updater.py` | Install/update/list game downloads |
| Game control | `actions/game_control.py` | Bounded input to active games |
| Game vision | `actions/game_vision.py` | Watch/analyze game screen |
| Steam Store | `actions/steam_store.py` | Price/store/Task Bar Hero helpers |

## Phone, Social, Smart Home

| Function | Module | Notes |
|---|---|---|
| iPhone bridge | `actions/iphone_bridge.py` | Phone Link/Bluetooth/URI helpers |
| iPhone Shortcuts | `actions/iphone_shortcuts.py` | Local shortcut event bridge |
| Social control | `actions/social_control.py` | WhatsApp/Instagram web/app helpers |
| Smart home | `actions/smart_home.py` | Smart-home and Spotify bridge |
| Spotify control | `actions/spotify_control.py` | Playback/device/account actions |

## Coding and Developer Tools

| Function | Module | Notes |
|---|---|---|
| Code helper | `actions/code_helper.py` | Coding help workflows |
| Dev agent | `actions/dev_agent.py` | Developer task support |
| Local LLM | `actions/local_llm.py` | Ollama status, presets, local answers |

## Local/Private Files Not For GitHub

Keep these local unless converted into safe examples:

- `config/api_keys.json`
- `config/*credentials*.json`
- `memory/long_term.json`
- `memory/neural_activity.json`
- `memory/*state.json`
- `memory/*index*.json`
- `memory/sound_samples/`
- face data, screenshots, personal vault exports, and generated Obsidian dumps