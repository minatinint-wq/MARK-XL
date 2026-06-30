import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _get_os() -> str:
    try:
        cfg = json.loads(
            (_base_dir() / "config" / "api_keys.json").read_text(encoding="utf-8")
        )
        return cfg.get("os_system", "windows").lower()
    except Exception:
        return "windows"


def _scripts_dir() -> Path:
    d = Path.home() / ".jarvis" / "reminders"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index_path() -> Path:
    return _scripts_dir() / "index.json"


def _sanitise(text: str, max_len: int = 200) -> str:
    return (
        text.replace("\\", "")
            .replace('"', "")
            .replace("'", "")
            .replace("\n", " ")
            .replace("\r", "")
            .strip()
    )[:max_len]


def _load_index() -> dict:
    path = _index_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("jobs", [])
            return data
    except Exception:
        pass
    return {"jobs": []}


def _save_index(data: dict) -> None:
    _index_path().write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _record_job(meta: dict) -> None:
    data = _load_index()
    jobs = [job for job in data.get("jobs", []) if job.get("task_name") != meta.get("task_name")]
    jobs.append(meta)
    data["jobs"] = jobs
    _save_index(data)


def _remove_job(task_name: str) -> None:
    data = _load_index()
    data["jobs"] = [job for job in data.get("jobs", []) if job.get("task_name") != task_name]
    _save_index(data)


def _write_notify_script(
    task_name: str,
    message: str,
    os_name: str,
    kind: str = "reminder",
    duration_seconds: int = 0,
) -> Path:
    script_path = _scripts_dir() / f"{task_name}.py"
    msg_literal = json.dumps(message)  
    title = "J.A.R.V.I.S Alarm" if kind == "alarm" else "J.A.R.V.I.S Reminder"
    title_literal = json.dumps(title)
    duration_seconds = max(0, min(int(duration_seconds or 0), 600))

    if os_name == "windows":
        notify_block = f"""
message = {msg_literal}
title = {title_literal}
notified = False

try:
    from plyer import notification
    notification.notify(title=title, message=message, timeout=20)
    notified = True
except Exception:
    pass

if not notified:
    try:
        from win10toast import ToastNotifier
        ToastNotifier().show_toast(title, message, duration=20, threaded=False)
        notified = True
    except Exception:
        pass

if not notified:
    try:
        import subprocess
        subprocess.run(["msg", "*", "/TIME:30", message], check=False)
    except Exception:
        pass

try:
    import time
    import winsound
    end_at = time.time() + {duration_seconds if kind == "alarm" else 1}
    pattern = [880, 1040, 1320, 1040] if {kind == "alarm"!r} else [800, 1000, 1200]
    while time.time() < end_at:
        for freq in pattern:
            winsound.Beep(freq, 220)
            time.sleep(0.08)
            if time.time() >= end_at:
                break
except Exception:
    pass
"""

    elif os_name == "mac":
        notify_block = f"""
message = {msg_literal}
title = {title_literal}
notified = False

try:
    from plyer import notification
    notification.notify(title=title, message=message, timeout=20)
    notified = True
except Exception:
    pass

if not notified:
    try:
        import subprocess
        script = 'display notification "{{}}" with title "{{}}"'.format(
            message.replace('"', ''), title.replace('"', '')
        )
        subprocess.run(["osascript", "-e", script], check=False)
    except Exception:
        pass

if {kind == "alarm"!r}:
    try:
        import subprocess, time
        end_at = time.time() + {duration_seconds}
        while time.time() < end_at:
            subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], check=False)
            time.sleep(0.2)
    except Exception:
        pass
"""

    else:  # linux
        notify_block = f"""
message = {msg_literal}
title = {title_literal}
notified = False

try:
    from plyer import notification
    notification.notify(title=title, message=message, timeout=20)
    notified = True
except Exception:
    pass

if not notified:
    try:
        import subprocess
        subprocess.run(
            ["notify-send", "--urgency=normal", "--expire-time=15000",
             title, message],
            check=False
        )
    except Exception:
        pass

if {kind == "alarm"!r}:
    try:
        import subprocess, time
        end_at = time.time() + {duration_seconds}
        while time.time() < end_at:
            subprocess.run(["paplay", "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"], check=False)
            time.sleep(0.2)
    except Exception:
        pass
"""

    script_body = f"""# Auto-generated by J.A.R.V.I.S reminder — do not edit
import sys, os, pathlib
{notify_block}
# Self-delete after firing
try:
    pathlib.Path(__file__).unlink(missing_ok=True)
except Exception:
    pass
"""
    script_path.write_text(script_body, encoding="utf-8")
    script_path.chmod(0o600)   # owner read/write only
    return script_path

def _schedule_windows(target_dt: datetime, task_name: str,
                      script_path: Path, message: str) -> str:
    python_exe = Path(sys.executable)
    pythonw = python_exe.parent / "pythonw.exe"
    if pythonw.exists():
        python_exe = pythonw

    xml_path = _scripts_dir() / f"{task_name}.xml"
    xml_content = (
        '<?xml version="1.0" encoding="UTF-16"?>\n'
        '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\n'
        '  <RegistrationInfo><Description>J.A.R.V.I.S Reminder</Description></RegistrationInfo>\n'
        '  <Triggers><TimeTrigger>\n'
        f'    <StartBoundary>{target_dt.strftime("%Y-%m-%dT%H:%M:%S")}</StartBoundary>\n'
        '    <Enabled>true</Enabled>\n'
        '  </TimeTrigger></Triggers>\n'
        '  <Actions><Exec>\n'
        f'    <Command>{python_exe}</Command>\n'
        f'    <Arguments>"{script_path}"</Arguments>\n'
        '  </Exec></Actions>\n'
        '  <Settings>\n'
        '    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>\n'
        '    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>\n'
        '    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>\n'
        '    <StartWhenAvailable>true</StartWhenAvailable>\n'
        '    <ExecutionTimeLimit>PT5M</ExecutionTimeLimit>\n'
        '    <Enabled>true</Enabled>\n'
        '  </Settings>\n'
        '  <Principals><Principal>\n'
        '    <LogonType>InteractiveToken</LogonType>\n'
        '    <RunLevel>LeastPrivilege</RunLevel>\n'
        '  </Principal></Principals>\n'
        '</Task>'
    )

    xml_path.write_text(xml_content, encoding="utf-16")

    result = subprocess.run(
        ["schtasks", "/Create", "/TN", task_name, "/XML", str(xml_path), "/F"],
        capture_output=True, text=True,
    )

    try:
        xml_path.unlink(missing_ok=True)
    except Exception:
        pass

    if result.returncode != 0:
        script_path.unlink(missing_ok=True)
        err = (result.stderr or result.stdout).strip()
        print(f"[Reminder] ❌ schtasks: {err}")
        return ""  

    return task_name


def _schedule_mac(target_dt: datetime, task_name: str,
                  script_path: Path) -> str:
    agents_dir = Path.home() / "Library" / "LaunchAgents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    label     = f"com.jarvis.reminder.{task_name}"
    plist_path = agents_dir / f"{label}.plist"

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>             <string>{label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{sys.executable}</string>
    <string>{script_path}</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Year</key>   <integer>{target_dt.year}</integer>
    <key>Month</key>  <integer>{target_dt.month}</integer>
    <key>Day</key>    <integer>{target_dt.day}</integer>
    <key>Hour</key>   <integer>{target_dt.hour}</integer>
    <key>Minute</key> <integer>{target_dt.minute}</integer>
  </dict>
  <key>RunAtLoad</key>         <false/>
  <key>StandardOutPath</key>   <string>/dev/null</string>
  <key>StandardErrorPath</key> <string>/dev/null</string>
</dict>
</plist>
"""
    plist_path.write_text(plist_content, encoding="utf-8")
    plist_path.chmod(0o644)

    result = subprocess.run(
        ["launchctl", "load", str(plist_path)],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        plist_path.unlink(missing_ok=True)
        script_path.unlink(missing_ok=True)
        print(f"[Reminder] ❌ launchctl: {result.stderr.strip()}")
        return ""

    return label


def _schedule_linux(target_dt: datetime, task_name: str,
                    script_path: Path) -> str:

    if shutil.which("systemd-run"):
        on_calendar = target_dt.strftime("%Y-%m-%d %H:%M:00")
        result = subprocess.run(
            [
                "systemd-run",
                "--user",
                f"--on-calendar={on_calendar}",
                f"--unit={task_name}",
                "--",
                sys.executable, str(script_path),
            ],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return task_name
        print(f"[Reminder] ⚠️ systemd-run failed: {result.stderr.strip()}, trying 'at'")

    if shutil.which("at"):
        at_time = target_dt.strftime("%H:%M %Y-%m-%d")
        cmd_str = f"{sys.executable} {script_path}\n"
        result  = subprocess.run(
            ["at", at_time],
            input=cmd_str, capture_output=True, text=True,
        )
        if result.returncode == 0:
            return task_name
        print(f"[Reminder] ❌ at: {result.stderr.strip()}")
        return ""

    print("[Reminder] ❌ Neither systemd-run nor at found on this Linux system.")
    return ""


def _target_datetime(parameters: dict) -> tuple[datetime | None, str | None]:
    now = datetime.now()

    try:
        seconds = float(parameters.get("seconds") or 0)
        minutes = float(parameters.get("minutes") or 0)
        hours = float(parameters.get("hours") or 0)
    except Exception:
        seconds = minutes = hours = 0

    if seconds or minutes or hours:
        return now + timedelta(seconds=seconds, minutes=minutes, hours=hours), None

    date_str = str(parameters.get("date", "")).strip()
    time_str = str(parameters.get("time", "")).strip()

    if not date_str and time_str:
        date_str = now.strftime("%Y-%m-%d")
    if not date_str or not time_str:
        return None, "Preciso de date+time ou minutes/hours/seconds para agendar."

    try:
        return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M"), None
    except ValueError:
        return None, "Não consegui ler data/hora. Use YYYY-MM-DD e HH:MM, ou minutes=10."


def _list_jobs(kind_filter: str = "") -> str:
    data = _load_index()
    now = datetime.now()
    jobs = []
    changed = False

    for job in data.get("jobs", []):
        try:
            target = datetime.fromisoformat(job.get("target", ""))
        except Exception:
            target = None
        if target and target < now - timedelta(days=1):
            changed = True
            continue
        if kind_filter and job.get("kind") != kind_filter:
            continue
        jobs.append(job)

    if changed:
        data["jobs"] = [job for job in data.get("jobs", []) if job in jobs or (kind_filter and job.get("kind") != kind_filter)]
        _save_index(data)

    if not jobs:
        return "Nenhum alarme/lembrete agendado."

    lines = ["Alarmes/lembretes agendados:"]
    for idx, job in enumerate(sorted(jobs, key=lambda item: item.get("target", "")), 1):
        try:
            target = datetime.fromisoformat(job.get("target", ""))
            when = target.strftime("%Y-%m-%d %H:%M")
        except Exception:
            when = job.get("target", "?")
        lines.append(
            f"{idx}. {job.get('kind', 'reminder')} · {when} · "
            f"{job.get('message', '')} · id={job.get('task_name', '')}"
        )
    return "\n".join(lines)


def _match_job(query: str) -> dict | None:
    data = _load_index()
    jobs = data.get("jobs", [])
    query = str(query or "").strip().lower()
    if not query and jobs:
        return sorted(jobs, key=lambda item: item.get("target", ""))[0]

    for job in jobs:
        haystack = " ".join(
            str(job.get(key, "")) for key in ("task_name", "message", "label", "kind")
        ).lower()
        if query in haystack:
            return job
    return None


def _cancel_scheduled_job(job: dict) -> str:
    task_name = job.get("task_name", "")
    os_name = job.get("os") or _get_os()
    if not task_name:
        return "Esse alarme nao tem task_name salvo."

    ok = False
    if os_name == "windows":
        result = subprocess.run(
            ["schtasks", "/Delete", "/TN", task_name, "/F"],
            capture_output=True,
            text=True,
        )
        ok = result.returncode == 0
    elif os_name == "mac":
        label = job.get("job_id", task_name)
        plist = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
        subprocess.run(["launchctl", "unload", str(plist)], capture_output=True, text=True)
        plist.unlink(missing_ok=True)
        ok = True
    else:
        subprocess.run(["systemctl", "--user", "stop", task_name], capture_output=True, text=True)
        ok = True

    try:
        script = Path(job.get("script_path", ""))
        script.unlink(missing_ok=True)
    except Exception:
        pass

    _remove_job(task_name)
    return f"Cancelado: {task_name}" if ok else f"Nao consegui cancelar no sistema, mas removi do indice: {task_name}"


def reminder(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    parameters = parameters or {}
    action = str(parameters.get("action") or "set").lower().strip()

    if action in ("list", "listar", "status", "alarms", "alarm_list"):
        return _list_jobs(str(parameters.get("type") or parameters.get("kind") or ""))

    if action in ("cancel", "delete", "remove", "apagar", "cancelar", "stop_alarm"):
        query = parameters.get("id") or parameters.get("name") or parameters.get("label") or parameters.get("message") or ""
        job = _match_job(str(query))
        if not job:
            return "Nao encontrei esse alarme/lembrete para cancelar."
        return _cancel_scheduled_job(job)

    kind = "alarm" if action in ("alarm", "set_alarm", "alarme", "pc_alarm") or parameters.get("type") == "alarm" else "reminder"
    message = str(parameters.get("message") or parameters.get("text") or ("Alarme" if kind == "alarm" else "Reminder")).strip()
    target_dt, error = _target_datetime(parameters)
    if error:
        return error

    if target_dt <= datetime.now():
        return "Esse horário já passou. Não consigo agendar no passado."

    os_name    = _get_os()
    safe_msg   = _sanitise(message)
    prefix     = "JARVISAlarm" if kind == "alarm" else "JARVISReminder"
    task_name  = f"{prefix}_{target_dt.strftime('%Y%m%d_%H%M%S')}"
    duration_seconds = int(parameters.get("duration_seconds") or parameters.get("duration") or (60 if kind == "alarm" else 1))

    if bool(parameters.get("dry_run", False)):
        return f"DRY RUN: {kind} em {target_dt.strftime('%Y-%m-%d %H:%M')} — {safe_msg}"

    try:
        script_path = _write_notify_script(task_name, safe_msg, os_name, kind=kind, duration_seconds=duration_seconds)
    except Exception as e:
        return f"Não consegui preparar o script do alarme: {e}"

    try:
        if os_name == "windows":
            job_id = _schedule_windows(target_dt, task_name, script_path, safe_msg)
        elif os_name == "mac":
            job_id = _schedule_mac(target_dt, task_name, script_path)
        else:
            job_id = _schedule_linux(target_dt, task_name, script_path)
    except Exception as e:
        script_path.unlink(missing_ok=True)
        print(f"[Reminder] ❌ Scheduling exception: {e}")
        return "Algo deu errado ao agendar no sistema."

    if not job_id:
        return "Não consegui registrar no agendador do sistema."

    _record_job({
        "kind": kind,
        "task_name": task_name,
        "job_id": job_id,
        "target": target_dt.isoformat(timespec="minutes"),
        "message": safe_msg,
        "label": parameters.get("label") or parameters.get("name") or "",
        "script_path": str(script_path),
        "os": os_name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "duration_seconds": duration_seconds,
    })

    if player:
        player.write_log(f"[Reminder] ✅ {target_dt.strftime('%Y-%m-%d %H:%M')} — {safe_msg[:40]}")

    friendly_time = target_dt.strftime("%d/%m/%Y às %H:%M")
    if kind == "alarm":
        return f"Alarme programado para {friendly_time}: {safe_msg}"
    return f"Lembrete programado para {friendly_time}: {safe_msg}"
