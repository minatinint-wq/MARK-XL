import json
import re
import sys
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"


PLANNER_PROMPT = """You are the planning module of MARK XXV, a personal AI assistant.
Your job: break any user goal into a sequence of steps using ONLY the tools listed below.

ABSOLUTE RULES:
- NEVER use generated_code or write Python scripts. It does not exist.
- NEVER reference previous step results in parameters. Every step is independent.
- Use web_search for public information retrieval, research, or current data.
- Use obsidian_control for Obsidian vault notes, brain memory notes, categories, tags, frontmatter, and moving notes.
- Use file_controller to save generic files to disk.
- Use game_updater for installing, updating, listing, and checking downloads for Steam/Epic games.
- Use game_control for controlling an already-open game with keyboard/mouse input.
- Use quick_command for saved standard commands/macros like abrir mine, abrir brawlhalla, formulas, calculations, and saved user shortcuts.
- Max 5 steps. Use the minimum steps needed.

AVAILABLE TOOLS AND THEIR PARAMETERS:

open_app
  app_name: string (required)

web_search
  query: string (required) — write a clear, focused search query
  mode: "search" or "compare" (optional, default: search)
  items: list of strings (optional, for compare mode)
  aspect: string (optional, for compare mode)

maps_mode
  action: "tempo" | "rota" | "cep" | "search" | "open" | "navegar" | "reverse" | "set_default" | "status" (required)
  origin/origem: string (for tempo/rota)
  destination/destino/query: string (destination or address)
  cep: string (for Brazilian CEP lookup)
  mode: "driving" | "walking" | "bicycling" | "transit" (optional)
  open: boolean (open Google Maps)

game_updater
  action: "update" | "install" | "list" | "download_status" | "schedule" (required)
  platform: "steam" | "epic" | "both" (optional, default: both)
  game_name: string (optional)
  app_id: string (optional)
  shutdown_when_done: boolean (optional)

game_control
  action: "status" | "focus" | "launch" | "tap" | "hold" | "key_down" | "key_up" | "combo" | "mouse" | "sequence" | "stop" | "profile" | "forward" | "back" | "left" | "right" | "jump" | "crouch" | "sprint" | "interact" | "reload" | "inventory" | "map" | "pause" (required)
  game: string (optional window title/profile)
  key: string (for tap/hold/key_down/key_up)
  keys: string (for combo, e.g. "alt+tab")
  seconds: number (for hold, capped)
  dx, dy: int (for mouse look/aim)
  dry_run: boolean (optional)

browser_control
  action: "go_to" | "search" | "click" | "type" | "scroll" | "get_text" | "press" | "close" | "spotify" (required)
  url: string (for go_to)
  query: string (for search)
  text: string (for click/type)
  direction: "up" | "down" (for scroll)
  command: string (for spotify: "play_liked", "current", "next", "previous")

file_controller
  action: "write" | "create_file" | "read" | "list" | "delete" | "move" | "copy" | "find" | "disk_usage" (required)
  path: string — use "desktop" for Desktop folder
  name: string — filename
  content: string — file content (for write/create_file)

obsidian_control
  action: "status" | "categories" | "list" | "search" | "read" | "create" | "append" | "replace" | "frontmatter" | "tag" | "remove_tag" | "move" | "rename" | "archive" | "backlinks" | "open" | "daily" | "organize" (required)
  query: string (for search/read/move by note title)
  category: string (optional source category)
  destination: string (for move)
  title: string (for create)
  content: string (for create/append/replace)
  tag: string (for tag/remove_tag)

computer_settings
  action: string (required)
  description: string — natural language description
  value: string (optional)

computer_control
  action: "type" | "click" | "hotkey" | "press" | "key_down" | "key_up" | "hold" | "scroll" | "move" | "mouse_relative" | "position" | "read_clipboard" | "copy" | "set_clipboard" | "paste_clipboard" | "screenshot" | "screen_find" | "screen_click" (required)
  text: string (for type)
  x, y: int (for click)
  dx, dy: int (for mouse_relative)
  keys: string (for hotkey, e.g. "ctrl+c")
  key: string (for press)
  direction: "up" | "down" (for scroll)
  description: string (for screen_find/screen_click)

quick_command
  action: "run" | "list" | "show" | "save" | "delete" | "calculate" | "search" | "formula" (required)
  name: string (saved command name for run/show/save/delete)
  command: string (natural command phrase, e.g. "abrir mine")
  query: string (for search/formula/run variables)
  expression: string (for calculate)
  app_name: string (shortcut when saving/opening an app command)
  aliases: list of strings (optional)
  steps: list of objects (optional macro steps)

screen_process
  text: string (required) — what to analyze or ask about the screen
  angle: "screen" | "camera" (optional)

send_message
  receiver: string (required)
  message_text: string (required)
  platform: string (required)

reminder
  action: "set" | "set_alarm" | "list" | "cancel" (optional)
  date: string YYYY-MM-DD (for absolute schedule)
  time: string HH:MM (for absolute schedule)
  minutes: number (for relative timer/alarm)
  hours: number (for relative timer/alarm)
  message: string
  duration_seconds: integer (for alarm sound duration)

desktop_control
  action: "wallpaper" | "organize" | "clean" | "list" | "task" (required)
  path: string (optional)
  task: string (optional)

youtube_video
  action: "play" | "summarize" | "trending" (required)
  query: string (for play)

weather_report
  action: "forecast" | "current" | "today" | "tomorrow" | "rain" | "open" (optional)
  city/cidade/location/query: string (city, address, or natural weather query)
  cep: string (Brazilian CEP)
  lat/lon: string (coordinates)
  days: integer 1-7
  when: string (today/tomorrow/date-ish)

spotify_control
  action: "play" | "pause" | "next" | "previous" | "shuffle" | "repeat" | "liked" | "current" | "volume_up" | "volume_down" | "search" | "playlist" | "home" | "queue" | "lyrics" | "devices" (required)
  query: string (optional, for search)

flight_finder
  origin: string (required)
  destination: string (required)
  date: string (required)

code_helper
  action: "write" | "edit" | "run" | "explain" (required)
  description: string (required)
  language: string (optional)
  output_path: string (optional)
  file_path: string (optional)

dev_agent
  description: string (required)
  language: string (optional)
EXAMPLES:

Goal: "research mechanical engineering and save it to a notepad file"
Steps:

web_search | query: "mechanical engineering overview definition history"
web_search | query: "mechanical engineering applications and future trends"
file_controller | action: write, path: desktop, name: mechanical_engineering.txt, content: "MECHANICAL ENGINEERING RESEARCH\n\nThis file will be filled with web research results."

Goal: "What is the price of Bitcoin"
Steps:

web_search | query: "Bitcoin price today USD"

Goal: "List the files on the desktop and find the largest 5 files"
Steps:

file_controller | action: list, path: desktop
file_controller | action: largest, path: desktop, count: 5

Goal: "Move the Obsidian note TBH: Task Bar Hero from imoveis to games"
Steps:

obsidian_control | action: move, query: "TBH: Task Bar Hero", category: imoveis, destination: games

Goal: "Install PUBG from Steam"
Steps:

game_updater | action: install, platform: steam, game_name: "PUBG"

Goal: "Update all my Steam games"
Steps:

game_updater | action: update, platform: steam

Goal: "In the game, hold W for two seconds and jump"
Steps:

game_control | action: hold, key: w, seconds: 2
game_control | action: jump

Goal: "Play music on Spotify"
Steps:

spotify_control | action: play

Goal: "Pause the music"
Steps:

spotify_control | action: pause

Goal: "Next song on Spotify"
Steps:

spotify_control | action: next

Goal: "Play liked songs on Spotify"
Steps:

open_app | app_name: "Spotify"
spotify_control | action: liked

Goal: "Send John a message on WhatsApp saying there is a meeting tomorrow"
Steps:

send_message | receiver: John, message_text: "There is a meeting tomorrow", platform: WhatsApp

Goal: "Set an alarm on the PC for 30 minutes later"
Steps:

reminder | action: set_alarm, minutes: 30, message: "Alarme"

OUTPUT — return ONLY valid JSON, no markdown, no explanation, no code blocks:
{
  "goal": "...",
  "steps": [
    {
      "step": 1,
      "tool": "tool_name",
      "description": "what this step does",
      "parameters": {},
      "critical": true
    }
  ]
}
"""


def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


def create_plan(goal: str, context: str = "") -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=_get_api_key())

    user_input = f"Goal: {goal}"
    if context:
        user_input += f"\n\nContext: {context}"

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=user_input,
            config=types.GenerateContentConfig(system_instruction=PLANNER_PROMPT),
        )
        text     = response.text.strip()
        text     = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()

        plan = json.loads(text)

        if "steps" not in plan or not isinstance(plan["steps"], list):
            raise ValueError("Invalid plan structure")

        for step in plan["steps"]:
            if step.get("tool") in ("generated_code",):
                print(f"[Planner] ⚠️ generated_code detected in step {step.get('step')} — replacing with web_search")
                desc = step.get("description", goal)
                step["tool"] = "web_search"
                step["parameters"] = {"query": desc[:200]}

        print(f"[Planner] ✅ Plan: {len(plan['steps'])} steps")
        for s in plan["steps"]:
            print(f"  Step {s['step']}: [{s['tool']}] {s['description']}")

        return plan

    except json.JSONDecodeError as e:
        print(f"[Planner] ⚠️ JSON parse failed: {e}")
        return _fallback_plan(goal)
    except Exception as e:
        print(f"[Planner] ⚠️ Planning failed: {e}")
        return _fallback_plan(goal)


def _fallback_plan(goal: str) -> dict:
    print("[Planner] 🔄 Fallback plan")
    goal_lower = goal.lower()
    if any(word in goal_lower for word in ("mover", "move", "mova")) and any(word in goal_lower for word in ("nota", "obsidian", "vault", "categoria")):
        target = _extract_note_target(goal)
        destination = "games" if any(word in goal_lower for word in ("games", "jogos", "jogo")) else ""
        category = "imoveis" if any(word in goal_lower for word in ("imoveis", "imóveis", "imobili")) else ""
        return {
            "goal": goal,
            "steps": [
                {
                    "step": 1,
                    "tool": "obsidian_control",
                    "description": "Move the Obsidian note mentioned in the goal.",
                    "parameters": {
                        "action": "move" if destination else "search",
                        "query": target,
                        "category": category,
                        "destination": destination,
                    },
                    "critical": True,
                }
            ],
        }
    if any(word in goal_lower for word in ("mover", "move", "mova")) and any(word in goal_lower for word in ("arquivo", "file")):
        quoted = re.findall(r'"([^"]+)"|“([^”]+)”|\'([^\']+)\'', goal)
        target = next((part for match in quoted for part in match if part), goal[:80])
        return {
            "goal": goal,
            "steps": [
                {
                    "step": 1,
                    "tool": "file_controller",
                    "description": "Find the local file mentioned in the goal.",
                    "parameters": {"action": "find", "path": "D:\\xxxx_memory", "name": target},
                    "critical": True,
                }
            ],
        }
    if _looks_like_game_control(goal_lower):
        return {
            "goal": goal,
            "steps": [
                {
                    "step": 1,
                    "tool": "game_control",
                    "description": "Control the active game with safe bounded input.",
                    "parameters": _fallback_game_params(goal_lower),
                    "critical": True,
                }
            ],
        }
    return {
        "goal": goal,
        "steps": [
            {
                "step": 1,
                "tool": "web_search",
                "description": f"Search for: {goal}",
                "parameters": {"query": goal},
                "critical": True
            }
        ]
    }


def _extract_note_target(goal: str) -> str:
    quoted = re.findall(r'"([^"]+)"|“([^”]+)”|\'([^\']+)\'', goal)
    target = next((part for match in quoted for part in match if part), "").strip()
    if target:
        return target

    lower = goal.lower()
    if "tbh" in lower and "task bar hero" in lower:
        return "TBH Task Bar Hero"

    marker = re.search(r"(?:sobre|chamada|chamado|nota)\s+(.+?)(?:\s+que\s+|\s+da\s+categoria|\s+para\s+|$)", goal, flags=re.IGNORECASE)
    if marker:
        return marker.group(1).strip(" .:")
    return goal[:80]


def _looks_like_game_control(goal_lower: str) -> bool:
    install_words = ("instalar", "install", "update", "atualizar", "download", "baixar")
    if any(word in goal_lower for word in install_words):
        return False
    game_words = ("jogo", "game", "gameplay", "teclado", "mouse", "mira", "mirar")
    control_words = ("segura", "segure", "hold", "aperta", "pressiona", "press", "pula", "jump", "anda", "move", "mira", "click", "para tudo", "solta")
    key_words = (" w", " a", " s", " d", "wasd", "space", "shift", "ctrl")
    return any(word in goal_lower for word in game_words + control_words + key_words)


def _fallback_game_params(goal_lower: str) -> dict:
    if any(word in goal_lower for word in ("para tudo", "panic", "stop", "solta", "solte")):
        return {"action": "stop"}
    key = ""
    for candidate in ("w", "a", "s", "d", "shift", "ctrl", "space"):
        if re.search(rf"\b{re.escape(candidate)}\b", goal_lower):
            key = candidate
            break
    seconds_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:s|seg|segundos|seconds)", goal_lower)
    seconds = float(seconds_match.group(1).replace(",", ".")) if seconds_match else 0.5
    wants_hold = key and any(word in goal_lower for word in ("segura", "segure", "hold"))
    wants_jump = any(word in goal_lower for word in ("pula", "jump"))
    wants_reload = any(word in goal_lower for word in ("recarrega", "reload"))
    wants_inventory = any(word in goal_lower for word in ("inventario", "inventário", "inventory"))
    if wants_hold and (wants_jump or wants_reload or wants_inventory):
        steps = [{"action": "hold", "key": key, "seconds": seconds}]
        if wants_jump:
            steps.append({"action": "tap", "command": "jump"})
        if wants_reload:
            steps.append({"action": "tap", "command": "reload"})
        if wants_inventory:
            steps.append({"action": "tap", "command": "inventory"})
        return {"action": "sequence", "steps": steps}
    if wants_hold:
        return {"action": "hold", "key": key, "seconds": seconds}
    if wants_jump:
        return {"action": "jump"}
    if wants_reload:
        return {"action": "reload"}
    if wants_inventory:
        return {"action": "inventory"}
    if any(word in goal_lower for word in ("mira", "aim", "look")):
        dx = 250 if any(word in goal_lower for word in ("direita", "right")) else -250 if any(word in goal_lower for word in ("esquerda", "left")) else 0
        dy = 180 if any(word in goal_lower for word in ("baixo", "down")) else -180 if any(word in goal_lower for word in ("cima", "up")) else 0
        return {"action": "mouse", "mode": "look", "dx": dx, "dy": dy}
    if key:
        return {"action": "tap", "key": key}
    return {"action": "status"}


def replan(goal: str, completed_steps: list, failed_step: dict, error: str) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=_get_api_key())

    completed_summary = "\n".join(
        f"  - Step {s['step']} ({s['tool']}): DONE" for s in completed_steps
    )

    prompt = f"""Goal: {goal}

Already completed:
{completed_summary if completed_summary else '  (none)'}

Failed step: [{failed_step.get('tool')}] {failed_step.get('description')}
Error: {error}

Create a REVISED plan for the remaining work only. Do not repeat completed steps."""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=PLANNER_PROMPT),
        )
        text     = response.text.strip()
        text     = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
        plan     = json.loads(text)

        for step in plan.get("steps", []):
            if step.get("tool") == "generated_code":
                step["tool"] = "web_search"
                step["parameters"] = {"query": step.get("description", goal)[:200]}

        print(f"[Planner] 🔄 Revised plan: {len(plan['steps'])} steps")
        return plan
    except Exception as e:
        print(f"[Planner] ⚠️ Replan failed: {e}")
        return _fallback_plan(goal)
