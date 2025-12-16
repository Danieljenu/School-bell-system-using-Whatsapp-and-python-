# whatsapp_integration.py
"""
WhatsApp integration for JOTHI School Bell System.
Drop this file into your project and run it.
Requires: flask, requests, openai, pyttsx3, pygame
"""

import os
import time
import json
import threading
from pathlib import Path
from flask import Flask, request
import requests

# -------------------------
# Optional imports from your main system.
# If these do not exist yet, small stub functions are provided below.
# Replace them with your real functions from your bell/assembly code.
# -------------------------
try:
    from school_bell_system import (
        play_audio_blocking,
        ringBell,
        BELL_SCHEDULES,
        list_schedule_names,
        get_schedule,
        update_schedule,
        rename_schedule,
        delete_schedule,
        ABOUT_US_TEXT,
        get_today_assembly_config,
        NATIONAL_ANTHEM_FILE,
        EXTRA1_FILE,
        EXTRA2_FILE,
        ring_assembly_bell,
    )
except Exception:
    # Stubs - used for local testing if your main file isn't available yet
    print("[WARN] Could not import main functions; using local stubs.")

    def play_audio_blocking(path):
        print("[STUB] would play:", path)

    def ringBell(times, audio_file="bell.mp3", today_only=False):
        print("[STUB] ringBell called with", times, "today_only=", today_only)

    BELL_SCHEDULES = {"Regular Day": ["08:30", "09:30"]}

    def list_schedule_names():
        return list(BELL_SCHEDULES.keys())

    def get_schedule(name):
        return BELL_SCHEDULES.get(name, [])

    def update_schedule(name, times):
        BELL_SCHEDULES[name] = times

    def rename_schedule(o, n):
        BELL_SCHEDULES[n] = BELL_SCHEDULES.pop(o)

    def delete_schedule(n):
        BELL_SCHEDULES.pop(n, None)

    ABOUT_US_TEXT = (
        "JOTHI - School Bell System\n\n"
        "This project is built as a tribute and a practical school bell/announcement system."
    )

    def get_today_assembly_config():
        # returns (weekday_index, day_name, cfg)
        return 0, "Monday", {
            "label": "English Day",
            "prayer": "english_prayer.mp3",
            "birthday": "english_birthday.mp3",
        }

    NATIONAL_ANTHEM_FILE = "national_anthem.mp3"
    EXTRA1_FILE = None
    EXTRA2_FILE = None

    def ring_assembly_bell(duration=5):
        print(f"[STUB] ring assembly bell for {duration} seconds")
        time.sleep(duration)

# -------------------------
# AUDIO & TTS helpers
# -------------------------
# Offline TTS using pyttsx3
try:
    import pyttsx3
except Exception:
    pyttsx3 = None

def speak_offline_local(text, rate=170):
    if not pyttsx3:
        print("[TTS offline] pyttsx3 not available. Text:", text)
        return
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", rate)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as e:
        print("[TTS offline] error:", e)

# Online OpenAI TTS wrapper (optional)
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

_openai_client = None

def _init_openai_client_from_file():
    global _openai_client
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key and Path("openai_key.txt").exists():
        key = Path("openai_key.txt").read_text(encoding="utf-8").strip()
    if not key or not OpenAI:
        _openai_client = None
        if not key:
            print("[OpenAI] No API key set. Online voices will not work.")
        else:
            print("[OpenAI] OpenAI SDK not installed.")
        return
    try:
        _openai_client = OpenAI(api_key=key)
        print("[OpenAI] client ready")
    except Exception as e:
        print("[OpenAI] init error:", e)
        _openai_client = None

_init_openai_client_from_file()

def tts_openai_online(text, voice="alloy", outfile="online_tts.mp3"):
    if not _openai_client:
        print("[OpenAI] no client. falling back offline.")
        speak_offline_local(text)
        return
    try:
        path = Path(outfile)
        with _openai_client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts", voice=voice, input=text
        ) as resp:
            resp.stream_to_file(path)
        # play using your audio player
        play_audio_blocking(str(path))
    except Exception as e:
        print("[OpenAI] online tts error:", e)
        speak_offline_local(text)

def speak_alloy_online(text):
    tts_openai_online(text, "alloy", "alloy_tts.mp3")

def speak_nova_online(text):
    tts_openai_online(text, "nova", "nova_tts.mp3")

def speak_onyx_online(text):
    tts_openai_online(text, "onyx", "onyx_tts.mp3")

# -------------------------
# Storage of credentials & authorized numbers (TEXT files)
# -------------------------
def load_wa_config():
    cfg = {"PHONE_NUMBER_ID": None, "ACCESS_TOKEN": None}
    p = Path("wa_config.txt")
    if not p.exists():
        return cfg
    for line in p.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg

def save_wa_config(phone_id, access_token):
    Path("wa_config.txt").write_text(
        f"PHONE_NUMBER_ID={phone_id}\nACCESS_TOKEN={access_token}\n", encoding="utf-8"
    )

def load_authorized_numbers():
    p = Path("authorized_numbers.txt")
    if not p.exists():
        return {}
    d = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        # format: +9198...:role  or just +9198...
        if ":" in s:
            num, role = s.split(":", 1)
            d[num.strip()] = role.strip()
        else:
            d[s] = "teacher"
    return d

def save_authorized_numbers(d):
    lines = []
    for num, role in d.items():
        lines.append(f"{num}:{role}")
    Path("authorized_numbers.txt").write_text("\n".join(lines), encoding="utf-8")

# load initial config
_cfg = load_wa_config()
AUTH_USERS = load_authorized_numbers()  # dict { "+91...": "teacher"|"admin"|"developer" }

def is_authorized(number):
    return number in AUTH_USERS

def get_role(number):
    return AUTH_USERS.get(number, "teacher")

# -------------------------
# Session state per sender (for multi-step flows)
# -------------------------
SESSIONS = {}  # sender -> { "expect":..., "data":..., "ts":... }

def set_session(sender, state, data=None):
    SESSIONS[sender] = {"expect": state, "data": data or {}, "ts": time.time()}

def clear_session(sender):
    if sender in SESSIONS:
        del SESSIONS[sender]

def get_session(sender):
    s = SESSIONS.get(sender)
    if not s:
        return None
    if time.time() - s["ts"] > 300:
        clear_session(sender)
        return None
    return s

# -------------------------
# WhatsApp Cloud API helpers & Flask app
# -------------------------
app = Flask(__name__)
WA_CFG = _cfg
PHONE_NUMBER_ID = WA_CFG.get("PHONE_NUMBER_ID")
ACCESS_TOKEN = WA_CFG.get("ACCESS_TOKEN")
VERIFY_TOKEN = os.getenv("JOTHI_VERIFY_TOKEN", "JOTHI_VERIFY")

def send_whatsapp_text(to_number, text):
    global PHONE_NUMBER_ID, ACCESS_TOKEN
    if not PHONE_NUMBER_ID or not ACCESS_TOKEN:
        print("[send] missing WA config")
        return False
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number.lstrip("+"),
        "type": "text",
        "text": {"body": text},
    }
    r = requests.post(url, headers=headers, json=payload)
    print("[send] status", r.status_code)
    return r.ok

def get_media_url(media_id):
    global ACCESS_TOKEN
    if not ACCESS_TOKEN:
        return None, None
    meta_url = f"https://graph.facebook.com/v20.0/{media_id}"
    params = {"fields": "url,mime_type"}
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    r = requests.get(meta_url, headers=headers, params=params)
    if r.status_code == 200:
        j = r.json()
        return j.get("url"), j.get("mime_type")
    print("[media] get url failed", r.status_code, r.text)
    return None, None

def download_media_file(url, media_id, mime_type):
    global ACCESS_TOKEN
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    r = requests.get(url, headers=headers, stream=True)
    if r.status_code == 200:
        ext = ".ogg" if "ogg" in mime_type else ".mp3" if "mpeg" in mime_type else ".bin"
        out = f"wa_media_{media_id}{ext}"
        with open(out, "wb") as f:
            for c in r.iter_content(4096):
                f.write(c)
        print("[media] saved", out)
        return out
    print("[media] download failed", r.status_code)
    return None

# -------------------------
# Webhook handlers
# -------------------------
@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    chal = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("[webhook] verified")
        return chal, 200
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    print("[webhook] payload:", json.dumps(data)[:1000])
    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                val = change.get("value", {})
                messages = val.get("messages")
                if not messages:
                    continue
                for msg in messages:
                    threading.Thread(target=process_incoming_message, args=(msg, val)).start()
    except Exception as e:
        print("[webhook] error:", e)
    return "EVENT_RECEIVED", 200

def normalize_number(n):
    if not n:
        return n
    if n.startswith("+"):
        return n
    return "+" + n

# -------------------------
# Core message processing & command handler
# -------------------------
def process_incoming_message(msg, val):
    sender = normalize_number(msg.get("from"))
    if not sender:
        return
    print("[msg] from", sender, "type", msg.get("type"))
    # if sender not authorized -> respond a default non-authorized message
    # TEMP: allow all users during testing
    #if not is_authorized(sender):
    #    send_whatsapp_text(sender, "Welcome to JOTHI WhatsApp bot. You are not authorized for commands. Contact admin.")
    #    return

    # if session pending expectant flow:
    session = get_session(sender)
    if session:
        handle_session_message(sender, session, msg)
        return

    # non-slash text => welcome prompt
    if msg.get("type") == "text":
        body = msg.get("text", {}).get("body", "").strip()
        if not body.startswith("/"):
            # non-slash greeting
            send_whatsapp_text(sender, "Welcome to JOTHI WhatsApp bot. Type /help to see commands.")
            return
        # else it's a slash command
        handle_slash_command(sender, body)
        return

    # audio directly (if user sends voice without a prior prompt)
    if msg.get("type") == "audio":
        # we only accept voice note for announcement when session expects it
        send_whatsapp_text(sender, "To use a voice note for announcement, please send /announce voice first.")
        return

    send_whatsapp_text(sender, "Message type not supported. Use /help")

def handle_session_message(sender, session, msg):
    expect = session["expect"]
    data = session["data"]
    print("[session] expecting", expect, "from", sender)

    if expect == "announce_model":
        if msg.get("type") != "text":
            send_whatsapp_text(sender, "Please send model number 1/2/3/4 as text.")
            return
        choice = msg.get("text", {}).get("body", "").strip()
        if choice not in ("1", "2", "3", "4"):
            send_whatsapp_text(sender, "Invalid choice. Send 1,2,3 or 4.")
            return
        model_map = {"1": "alloy", "2": "nova", "3": "onyx", "4": "offline"}
        model = model_map[choice]
        announce_text = data.get("announce_text", "")

        def run_announce():
            if model == "offline":
                speak_offline_local(announce_text)
            else:
                tts_openai_online(announce_text, voice=model, outfile=f"announce_{model}.mp3")

        threading.Thread(target=run_announce).start()
        send_whatsapp_text(sender, "Announcement played using model " + choice)
        clear_session(sender)
        return

    if expect == "announce_wait_voice":
        if msg.get("type") != "audio":
            send_whatsapp_text(sender, "Please send a voice note (audio message).")
            return
        media_id = msg.get("audio", {}).get("id")
        url, mime = get_media_url(media_id)
        if not url:
            send_whatsapp_text(sender, "Failed to get media URL.")
            clear_session(sender)
            return
        path = download_media_file(url, media_id, mime)
        if not path:
            send_whatsapp_text(sender, "Failed to download voice.")
            clear_session(sender)
            return
        threading.Thread(target=play_audio_blocking, args=(path,)).start()
        send_whatsapp_text(sender, "Voice announcement received and played.")
        clear_session(sender)
        return

    # other session types can be added
    send_whatsapp_text(sender, "Session expired or unknown.")
    clear_session(sender)

def handle_slash_command(sender, body):
    lower = body.strip()
    role = get_role(sender)

    if lower == "/help":
        if role == "teacher":
            send_whatsapp_text(sender, "JOTHI Commands (Teacher):\n/bellmode - Bell options\n/assembly - Assembly playback\n/about - About us")
            return
        if role == "admin":
            send_whatsapp_text(sender, "JOTHI Commands (Admin):\n/announcement - Make announcement\n/about - About us")
            return
        if role == "developer":
            send_whatsapp_text(sender, "JOTHI Commands (Developer):\n/bellmode\n/assembly\n/announcement\n/settings\n/about")
            return

    if lower.startswith("/about"):
        send_whatsapp_text(sender, ABOUT_US_TEXT[:1500])
        return

    # BELL MODE (teacher and developer)
    if lower.startswith("/bellmode"):
        if role not in ("teacher", "developer"):
            send_whatsapp_text(sender, "Not allowed.")
            return
        parts = lower.split(maxsplit=2)
        if len(parts) == 1:
            send_whatsapp_text(sender, "Bell commands:\n/bellmode today - set today's times\n/bellmode use <name> - use saved schedule")
            return
        if parts[1] == "today":
            send_whatsapp_text(sender, "Send times for TODAY as comma separated HH:MM values. Example: 09:00,10:30,12:00")
            set_session(sender, "bell_today_input", {})
            return
        if parts[1] == "use" and len(parts) >= 3:
            name = parts[2].strip()
            sched = get_schedule(name)
            if not sched:
                send_whatsapp_text(sender, f"Schedule '{name}' not found.")
                return
            threading.Thread(target=ringBell, args=(sched,), kwargs={"today_only": False}).start()
            send_whatsapp_text(sender, f"Started schedule '{name}'")
            return
        send_whatsapp_text(sender, "Unknown bellmode command.")
        return

    # /assembly (teacher and developer)
    if lower.startswith("/assembly"):
        if role not in ("teacher", "developer"):
            send_whatsapp_text(sender, "Not allowed.")
            return
        parts = lower.split()
        if len(parts) == 1:
            send_whatsapp_text(sender, "Assembly commands: /assembly <n>\n1=Prayer,2=Birthday,3=Anthem,4=Extra1,5=Extra2,6=Bell(5s),11=Prayer+Birthday")
            return
        cmd = parts[1]
        if cmd == "1":
            idx, day_name, cfg = get_today_assembly_config()
            threading.Thread(target=play_audio_blocking, args=(cfg["prayer"],)).start()
            send_whatsapp_text(sender, "Playing prayer.")
            return
        if cmd == "2":
            idx, day_name, cfg = get_today_assembly_config()
            threading.Thread(target=play_audio_blocking, args=(cfg["birthday"],)).start()
            send_whatsapp_text(sender, "Playing birthday song.")
            return
        if cmd == "3":
            threading.Thread(target=play_audio_blocking, args=(NATIONAL_ANTHEM_FILE,)).start()
            send_whatsapp_text(sender, "Playing national anthem.")
            return
        if cmd == "4":
            if EXTRA1_FILE:
                threading.Thread(target=play_audio_blocking, args=(EXTRA1_FILE,)).start()
                send_whatsapp_text(sender, "Playing Extra 1.")
            else:
                send_whatsapp_text(sender, "Extra 1 not set.")
            return
        if cmd == "5":
            if EXTRA2_FILE:
                threading.Thread(target=play_audio_blocking, args=(EXTRA2_FILE,)).start()
                send_whatsapp_text(sender, "Playing Extra 2.")
            else:
                send_whatsapp_text(sender, "Extra 2 not set.")
            return
        if cmd == "6":
            threading.Thread(target=ring_assembly_bell, args=(5,)).start()
            send_whatsapp_text(sender, "Rung assembly bell for 5 seconds.")
            return
        if cmd == "11":
            idx, day_name, cfg = get_today_assembly_config()
            def both():
                play_audio_blocking(cfg["prayer"])
                play_audio_blocking(cfg["birthday"])
            threading.Thread(target=both).start()
            send_whatsapp_text(sender, "Played prayer + birthday.")
            return
        send_whatsapp_text(sender, "Unknown assembly option.")
        return

    # ANNOUNCEMENT (admin and developer)
    if lower.startswith("/announcement") or lower.startswith("/announce"):
        if role not in ("admin", "developer"):
            send_whatsapp_text(sender, "Not allowed.")
            return
        parts = lower.split(maxsplit=2)
        if len(parts) >= 2 and parts[1] == "text":
            msg = parts[2] if len(parts) >= 3 else ""
            if not msg:
                send_whatsapp_text(sender, "Usage: /announce text <your message>")
                return
            set_session(sender, "announce_model", {"announce_text": msg})
            send_whatsapp_text(sender, "Choose voice model for announcement:\n1. Alloy (online)\n2. Nova (online)\n3. Onyx (online)\n4. Offline local\nSend 1/2/3/4 now.")
            return
        if len(parts) >= 2 and parts[1] == "voice":
            set_session(sender, "announce_wait_voice", {})
            send_whatsapp_text(sender, "Please send the voice note now (record & send voice message in WhatsApp).")
            return
        send_whatsapp_text(sender, "Announcement usage:\n/announce text <message>\n/announce voice")
        return

    # SETTINGS (developer only)
    if lower.startswith("/settings"):
        if role != "developer":
            send_whatsapp_text(sender, "Not allowed.")
            return
        parts = lower.split(maxsplit=2)
        if len(parts) == 1:
            send_whatsapp_text(sender, "Settings:\n/settings setwa <PHONE_ID>|<ACCESS_TOKEN>\n/settings setopenai <OPENAI_KEY>")
            return
        sub = parts[1]
        if sub == "setwa" and len(parts) >= 3:
            if "|" not in parts[2]:
                send_whatsapp_text(sender, "Use: /settings setwa PHONE_ID|ACCESS_TOKEN")
                return
            phone_id, token = parts[2].split("|", 1)
            save_wa_config(phone_id.strip(), token.strip())
            cfg = load_wa_config()
            global PHONE_NUMBER_ID, ACCESS_TOKEN
            PHONE_NUMBER_ID = cfg.get("PHONE_NUMBER_ID")
            ACCESS_TOKEN = cfg.get("ACCESS_TOKEN")
            send_whatsapp_text(sender, "WhatsApp config saved.")
            return
        if sub == "setopenai" and len(parts) >= 3:
            key = parts[2].strip()
            Path("openai_key.txt").write_text(key, encoding="utf-8")
            _init_openai_client_from_file()
            send_whatsapp_text(sender, "OpenAI key saved & loaded.")
            return
        send_whatsapp_text(sender, "Unknown settings command.")
        return

    # SCHEDULE CRUD for developer role
    if lower.startswith("/schedule") and role == "developer":
        parts = lower.split(maxsplit=2)
        cmd = parts[1] if len(parts) >= 2 else ""
        if cmd == "list":
            names = list_schedule_names()
            send_whatsapp_text(sender, "Saved schedules: " + (", ".join(names) if names else "(none)"))
            return
        if cmd == "create" and len(parts) >= 3:
            if "|" not in parts[2]:
                send_whatsapp_text(sender, "Use: /schedule create NAME|HH:MM,HH:MM")
                return
            name, times = parts[2].split("|", 1)
            times = [t.strip() for t in times.split(",") if t.strip()]
            update_schedule(name.strip(), times)
            send_whatsapp_text(sender, f"Schedule '{name.strip()}' created.")
            return
        if cmd == "delete" and len(parts) >= 3:
            name = parts[2].strip()
            delete_schedule(name)
            send_whatsapp_text(sender, f"Deleted schedule '{name}'.")
            return
        if cmd == "rename" and len(parts) >= 3:
            if "|" not in parts[2]:
                send_whatsapp_text(sender, "Use: /schedule rename OLD|NEW")
                return
            old, new = parts[2].split("|", 1)
            rename_schedule(old.strip(), new.strip())
            send_whatsapp_text(sender, f"Renamed '{old.strip()}' -> '{new.strip()}'")
            return
        send_whatsapp_text(sender, "Schedule commands for developer: list/create/rename/delete")
        return

    # unknown
    send_whatsapp_text(sender, "Unknown command. Type /help")

# -------------------------
# Simple shell settings utility (call from your shell menu)
# -------------------------
def shell_settings_menu():
    print("1. Change WhatsApp config (PHONE_ID and ACCESS_TOKEN)")
    print("2. Change OpenAI API key")
    print("3. Add/Remove authorized number")
    c = input("Choose: ").strip()
    if c == "1":
        pid = input("PHONE ID: ").strip()
        tok = input("ACCESS TOKEN: ").strip()
        save_wa_config(pid, tok)
        print("Saved.")
    elif c == "2":
        key = input("OpenAI Key: ").strip()
        Path("openai_key.txt").write_text(key, encoding="utf-8")
        _init_openai_client_from_file()
        print("Saved.")
    elif c == "3":
        print("Current authorized:", AUTH_USERS)
        num = input("Number (+91...): ").strip()
        role = input("Role (teacher/admin/developer): ").strip()
        AUTH_USERS[num] = role
        save_authorized_numbers(AUTH_USERS)
        print("Saved.")
    else:
        print("Cancelled")

# -------------------------
# Run server
# -------------------------
if __name__ == "__main__":
    print("Starting WhatsApp webhook server on port 5000")
    # reload config
    _cfg = load_wa_config()
    PHONE_NUMBER_ID = _cfg.get("PHONE_NUMBER_ID")
    ACCESS_TOKEN = _cfg.get("ACCESS_TOKEN")
    _init_openai_client_from_file()
    app.run(host="0.0.0.0", port=5000, debug=True)
