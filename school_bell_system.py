'''School Bell System using WhatsApp & Python automates daily school operations with smart bell scheduling, assembly audio control, announcements, and WhatsApp command support. Lightweight, reliable, menu-driven, and dedicated to Mrs. Jyothi Suresh for her inspiration and guidance'''
import time
from datetime import datetime, date
import pygame
import sys
import time
import pyttsx3
import os
from pathlib import Path
from openai import OpenAI  


# -------------------------------------------------------------
# GLOBAL MODE FLAG
# -------------------------------------------------------------

CURRENT_MODE = "IDLE"   # IDLE / BELL / ASSEMBLY / ANNOUNCEMENT

def set_mode(mode: str):
    global CURRENT_MODE
    CURRENT_MODE = mode
    print(f"\n[MODE] Switched to: {CURRENT_MODE}\n")


# -------------------------------------------------------------
# AUDIO INITIALIZATION
# -------------------------------------------------------------

_audio_inited = False

def init_audio():
    global _audio_inited
    if not _audio_inited:
        pygame.mixer.init()
        _audio_inited = True

def play_audio_blocking(path: str):
    """Play an audio file fully, blocking until it finishes."""
    init_audio()
    pygame.mixer.music.load(path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)


# -------------------------------------------------------------
# TIME PARSER (for bell times, accepts 9, 9:30, 9am, 9:30 pm, 21:00)
# -------------------------------------------------------------

def parse_time_to_24h(t: str) -> str:
    """
    Convert a user time string to 'HH:MM' 24h format.
    Examples accepted:
      '9', '09', '9:00', '9:30', '09:30', '9am', '9 am', '9:30pm', '21:00'
    Raises ValueError if invalid.
    """
    s = t.strip().lower()
    if not s:
        raise ValueError("Empty time")

    ampm = None
    if "am" in s:
        ampm = "am"
        s = s.replace("am", "")
    if "pm" in s:
        if ampm is not None:
            raise ValueError("Both AM and PM present")
        ampm = "pm"
        s = s.replace("pm", "")

    s = s.strip()

    if ":" in s:
        parts = s.split(":")
        if len(parts) != 2:
            raise ValueError("Invalid time format")
        h = int(parts[0])
        m = int(parts[1])
    else:
        h = int(s)
        m = 0

    if ampm == "am":
        if h == 12:
            h = 0
    elif ampm == "pm":
        if h != 12:
            h += 12

    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("Time out of range")

    return f"{h:02d}:{m:02d}"


# -------------------------------------------------------------
# BELL SCHEDULER
# -------------------------------------------------------------

def ringBell(schedule_list, audio_file='bell.mp3',
             check_interval=20, volume=0.8, today_only=False):
    """
    Bell scheduler:
    - schedule_list: list of 'HH:MM' strings (24h).
    - Rings ONLY when CURRENT_MODE == "BELL".
    - If today_only=True, stops automatically when the date changes.
    """
    if not schedule_list:
        print("No times given. Returning.")
        return

    init_audio()
    pygame.mixer.music.set_volume(volume)

    # validate and convert to set of (hour, minute)
    schedule = set()
    for t in schedule_list:
        try:
            h, m = map(int, t.split(":"))
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError
            schedule.add((h, m))
        except Exception:
            print(f"Invalid time format '{t}', must be HH:MM (24h)")
    if not schedule:
        print("No valid times after parsing. Returning.")
        return

    formatted = [format_time_tuple(h, m) for (h, m) in sorted(schedule)]
    print("Bell schedule at:", ", ".join(formatted))
    print("Scheduler running... (Ctrl+C to stop)\n")

    rung_today = set()
    start_date = date.today()

    try:
        while True:
            # If not in BELL mode, do nothing but wait
            if CURRENT_MODE != "BELL":
                time.sleep(check_interval)
                continue

            now = datetime.now()

            # if today_only and date changed -> stop
            if today_only and date.today() != start_date:
                print("Date changed. Today-only bell scheduler stopping.")
                break

            # reset rung_today at midnight anyway
            if date.today() != start_date and not today_only:
                start_date = date.today()
                rung_today.clear()

            hm = (now.hour, now.minute)
            if hm in schedule and hm not in rung_today:
                print(f"Ringing bell at {hm[0]:02d}:{hm[1]:02d}")
                pygame.mixer.music.load(audio_file)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.05)
                rung_today.add(hm)

            time.sleep(check_interval)

    except KeyboardInterrupt:
        print("Bell scheduler stopped.\n")


# -------------------------------------------------------------
# IN-MEMORY BELL SCHEDULES (ONLY PYTHON)
# -------------------------------------------------------------

BELL_SCHEDULES = {
    "Regular Day": ["08:30", "09:30", "10:30", "11:30", "12:30"],
    "Short Friday": ["08:30", "09:15", "10:00", "10:45"]
}

def list_schedule_names():
    return list(BELL_SCHEDULES.keys())

def get_schedule(name):
    return BELL_SCHEDULES.get(name, None)

def update_schedule(name, time_list):
    BELL_SCHEDULES[name] = time_list

def rename_schedule(old_name, new_name):
    if old_name in BELL_SCHEDULES:
        BELL_SCHEDULES[new_name] = BELL_SCHEDULES[old_name]
        del BELL_SCHEDULES[old_name]

def delete_schedule(name):
    if name in BELL_SCHEDULES:
        del BELL_SCHEDULES[name]


# -------------------------------------------------------------
# ASSEMBLY CONFIG
# -------------------------------------------------------------

NATIONAL_ANTHEM_FILE = "national_anthem.mp3"    # COMMON, not per day
ASSEMBLY_BELL_FILE   = "bell.mp3"               # COMMON
EXTRA1_FILE = None
EXTRA2_FILE = None

# Day config: Monday = 0
DAY_CONFIG = {
    0: {"label": "English Day",   "prayer": "english_prayer.mp3",   "birthday": "english_birthday.mp3"},
    1: {"label": "English Day",   "prayer": "english_prayer.mp3",   "birthday": "english_birthday.mp3"},
    2: {"label": "Hindi Day",     "prayer": "hindi_prayer.mp3",     "birthday": "hindi_birthday.mp3"},
    3: {"label": "English Day",   "prayer": "english_prayer.mp3",   "birthday": "english_birthday.mp3"},
    4: {"label": "Malayalam Day", "prayer": "malayalam_prayer.mp3", "birthday": "malayalam_birthday.mp3"}
}

DAY_NAMES = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

def get_today_assembly_config():
    idx = datetime.now().weekday()
    if idx not in DAY_CONFIG:
        raise ValueError(f"No assembly config for {DAY_NAMES[idx]}")
    return idx, DAY_NAMES[idx], DAY_CONFIG[idx]

def ring_assembly_bell(duration=5):
    init_audio()
    pygame.mixer.music.load(ASSEMBLY_BELL_FILE)
    pygame.mixer.music.play()
    time.sleep(duration)
    pygame.mixer.music.stop()


# -------------------------------------------------------------
# ASSEMBLY MENU
# -------------------------------------------------------------

def assembly_menu():
    set_mode("ASSEMBLY")

    while True:
        try:
            idx, day_name, cfg = get_today_assembly_config()
        except ValueError as e:
            print(e)
            input("Press Enter to return.")
            return

        print("\n========== ASSEMBLY MODE ==========")
        print(f"Today: {day_name} ({cfg['label']})")
        print("Prayer file      :", cfg["prayer"])
        print("Birthday file    :", cfg["birthday"])
        print("National Anthem  :", NATIONAL_ANTHEM_FILE)
        print("Extra 1          :", EXTRA1_FILE or "(not set)")
        print("Extra 2          :", EXTRA2_FILE or "(not set)")
        print("-----------------------------------")
        print("1. Play Prayer")
        print("2. Play Birthday Song")
        print("3. Play National Anthem")
        print("4. Play Extra Audio 1")
        print("5. Play Extra Audio 2")
        print("6. Ring Bell (5 sec)")
        print("0. Back to Main Menu")

        choice = input("Choose: ").strip()

        if choice == "1":
            play_audio_blocking(cfg["prayer"])

        elif choice == "2":
            play_audio_blocking(cfg["birthday"])

        elif choice == "3":
            play_audio_blocking(NATIONAL_ANTHEM_FILE)

        elif choice == "4":
            if EXTRA1_FILE:
                play_audio_blocking(EXTRA1_FILE)
            else:
                print("Extra Audio 1 not set.")

        elif choice == "5":
            if EXTRA2_FILE:
                play_audio_blocking(EXTRA2_FILE)
            else:
                print("Extra Audio 2 not set.")

        elif choice == "6":
            ring_assembly_bell(5)

        elif choice == "0":
            set_mode("IDLE")
            return

        else:
            print("Invalid choice.\n")

# -------------------------------------------------------------
# OPENAI API KEY MANAGEMENT
# -------------------------------------------------------------

API_KEY_FILE = "openai_key.txt"
_openai_client = None  # will hold OpenAI() client


def _init_openai_client():
    """(Re)initialize OpenAI client based on stored key."""
    global _openai_client

    # 1. Try env var first
    key = os.getenv("OPENAI_API_KEY", "").strip()

    # 2. If not in env, try file
    if not key and os.path.exists(API_KEY_FILE):
        try:
            with open(API_KEY_FILE, "r", encoding="utf-8") as f:
                key = f.read().strip()
        except Exception:
            key = ""

    if not key:
        _openai_client = None
        print("[OpenAI] No API key set. Online voices will not work.")
        return

    # Store to env too (optional but handy)
    os.environ["OPENAI_API_KEY"] = key

    try:
        _openai_client = OpenAI(api_key=key)
        print("[OpenAI] Client initialized.")
    except Exception as e:
        print("[OpenAI] Failed to initialize client:", e)
        _openai_client = None


def set_openai_api_key(new_key: str):
    """Set and save a new OpenAI API key."""
    new_key = new_key.strip()
    if not new_key:
        print("API key not changed (empty).")
        return

    # Save to file
    try:
        with open(API_KEY_FILE, "w", encoding="utf-8") as f:
            f.write(new_key)
        print("API key saved to", API_KEY_FILE)
    except Exception as e:
        print("Failed to save API key:", e)

    # Re-init client
    _init_openai_client()

# -------------------------------------------------------------
# ONLINE TTS (OpenAI) - 3 HUMAN VOICES
# -------------------------------------------------------------

def tts_openai_online(text: str, voice: str = "alloy", filename: str = "online_tts.mp3"):
    """
    Generate speech using OpenAI TTS and play it.
    - Requires internet + valid OpenAI API key.
    - voice: one of 'alloy', 'nova', 'onyx', etc.
    """
    global _openai_client

    if not _openai_client:
        print("[OpenAI] No client available. Check your API key in settings.")
        print("Falling back to offline voice...")
        speak_offline_local(text)
        return

    try:
        speech_file_path = Path(filename)

        # gpt-4o-mini-tts is the TTS model for voices
        with _openai_client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice=voice,
            input=text,
        ) as response:
            response.stream_to_file(speech_file_path)

        play_audio_file(speech_file_path)

    except Exception as e:
        print("[OpenAI] Online TTS error:", e)
        print("Falling back to offline voice...")
        speak_offline_local(text)


def speak_alloy_online(text: str):
    """Online voice 1 – Alloy: neutral, clear."""
    tts_openai_online(text, voice="alloy", filename="alloy_tts.mp3")


def speak_nova_online(text: str):
    """Online voice 2 – Nova: brighter, energetic."""
    tts_openai_online(text, voice="nova", filename="nova_tts.mp3")


def speak_onyx_online(text: str):
    """Online voice 3 – Onyx: deeper, serious."""
    tts_openai_online(text, voice="onyx", filename="onyx_tts.mp3")
# -------------------------------------------------------------
# OFFLINE TTS (NO INTERNET) - LOCAL VOICE
# -------------------------------------------------------------

def speak_offline_local(text: str, rate: int = 170):
    """
    Offline TTS using pyttsx3.
    Works without internet.
    Uses system default voice.
    """
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", rate)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as e:
        print("[Offline TTS] Error:", e)


# -------------------------------------------------------------
# ANNOUNCEMENT MENU (SHELL) - 3 ONLINE + 1 OFFLINE
# -------------------------------------------------------------

def announcement_menu():
    set_mode("ANNOUNCEMENT")

    while True:
        print("\n========== ANNOUNCEMENT MODE ==========")
        print("Choose a voice for the announcement:")
        print("1. Online – Alloy (Neutral, human-like)")
        print("2. Online – Nova  (Energetic, bright)")
        print("3. Online – Onyx  (Deep, serious)")
        print("4. Offline – Local System Voice")
        print("0. Back to Main Menu")
        choice = input("Choose: ").strip()

        if choice == "0":
            # set_mode("IDLE")
            return

        if choice not in ("1", "2", "3", "4"):
            print("Invalid choice.")
            continue

        print("\nType the message to be announced.")
        print("(Leave empty and press Enter to cancel.)")
        msg = input("Message: ").strip()

        if not msg:
            print("No message entered. Cancelled.")
            continue

        print("\nAnnouncing...")
        try:
            if choice == "1":
                speak_alloy_online(msg)
            elif choice == "2":
                speak_nova_online(msg)
            elif choice == "3":
                speak_onyx_online(msg)
            elif choice == "4":
                speak_offline_local(msg)
        except Exception as e:
            print("Error while speaking:", e)

# -------------------------------------------------------------
# openai settings MENU
# -------------------------------------------------------------

def openai_settings_menu():
    """Small submenu to view/change OpenAI API key."""
    while True:
        print("\n========== OPENAI SETTINGS ==========")
        print("1. Set / Change API Key")
        print("2. Test Online TTS (short sample)")
        print("0. Back")
        choice = input("Choose: ").strip()

        if choice == "0":
            return

        elif choice == "1":
            new_key = input("Enter new OpenAI API key: ").strip()
            set_openai_api_key(new_key)

        elif choice == "2":
            print("Testing online TTS with 'This is a test from JOTHI.'")
            speak_alloy_online("This is a test from JOTHI.")
        else:
            print("Invalid choice.")


# -------------------------------------------------------------
# SETTINGS MENU
# -------------------------------------------------------------

def settings_menu():
    global NATIONAL_ANTHEM_FILE, ASSEMBLY_BELL_FILE, EXTRA1_FILE, EXTRA2_FILE

    while True:
        print("\n========== SETTINGS ==========")
        print("1. Change National Anthem file (COMMON)")
        print("2. Change Assembly Bell file (COMMON)")
        print("3. Set Extra Audio 1")
        print("4. Set Extra Audio 2")
        print("5. Change Prayer/Birthday file for a specific day")
        print("6. OpenAI / Online Voice Settings")
        print("0. Back")
        choice = input("Choose: ").strip()

        if choice == "1":
            p = input("New anthem file: ").strip()
            if p: NATIONAL_ANTHEM_FILE = p

        elif choice == "2":
            p = input("New assembly bell file: ").strip()
            if p: ASSEMBLY_BELL_FILE = p

        elif choice == "3":
            p = input("Extra Audio 1 file: ").strip()
            if p: EXTRA1_FILE = p

        elif choice == "4":
            p = input("Extra Audio 2 file: ").strip()
            if p: EXTRA2_FILE = p

        elif choice == "5":
            print("Days: 0=Mon 1=Tue 2=Wed 3=Thu 4=Fri 5=Sat 6=Sun")
            try:
                d = int(input("Day index: ").strip())
            except:
                print("Invalid day.")
                continue

            if d not in DAY_CONFIG:
                DAY_CONFIG[d] = {"label": "", "prayer": "", "birthday": ""}

            new_prayer = input("New prayer file (blank=no change): ").strip()
            new_bday   = input("New birthday file (blank=no change): ").strip()
            new_label  = input("New label (blank=no change): ").strip()

            if new_prayer:
                DAY_CONFIG[d]["prayer"] = new_prayer
            if new_bday:
                DAY_CONFIG[d]["birthday"] = new_bday
            if new_label:
                DAY_CONFIG[d]["label"] = new_label
        elif choice == "6":
            openai_settings_menu()

        elif choice == "0":
            return

        else:
            print("Invalid choice.\n")

#--------------------------------------------------------------
#Add a small helper function to format time
#--------------------------------------------------------------

def format_time_tuple(h, m):
    suffix = "AM"
    if h == 0:
        hour = 12
    elif h < 12:
        hour = h
    elif h == 12:
        hour = 12
        suffix = "PM"
    else:
        hour = h - 12
        suffix = "PM"
    return f"{hour}:{m:02d} {suffix}"

# -------------------------------------------------------------
# BELL MENU (OPTION 1) - NEW VERSION
# -------------------------------------------------------------

def bell_menu():
    set_mode("BELL")

    while True:
        print("\n========== BELL MODE ==========")
        print("1. Set Today's Bell Times (only for today)")
        print("2. Use a Saved Schedule")
        print("3. Edit a Schedule (rename / timings)")
        print("4. Create New Schedule")
        print("5. Delete a Schedule")
        print("0. Back to Main Menu")

        choice = input("Choose: ").strip()

        # 1. Today's bell times (temporary)
        if choice == "1":
            todays_times = []
            print("\nEnter today's bell times.")
            print("Examples: 9, 9:30, 9am, 9:30pm, 14:00")
            print("Type 'done' when finished.\n")
            while True:
                t = input("Time: ").strip()
                if t.lower() == "done":
                    break
                try:
                    canonical = parse_time_to_24h(t)
                    todays_times.append(canonical)
                except Exception as e:
                    print("Invalid time:", e)

            print("\nToday's Bell Times:", todays_times)
            if todays_times:
                print("Starting today-only scheduler... (Ctrl+C to stop)\n")
                ringBell(todays_times, today_only=True)
            else:
                print("No times entered.")
 
        #Saved Schedules: IF WE ENTERS 0 ITS A BUG WHERE THE LAST Saved Schedu BELL WORKS (EVERY WHERE)
        #FIXED 
        # 2. Use saved schedule (FIXED)
        elif choice == "2":
            names = list_schedule_names()
            if not names:
                print("No saved schedules.")
                continue

            print("\nSaved Schedules:")
            for i, n in enumerate(names):
                 print(f"{i+1}. {n}") 
            print("0. Back") 

            choice_idx = input("Choose: ").strip()

            if choice_idx == "0":
                continue  # safely return to Bell menu

            if not choice_idx.isdigit():
                print("Invalid choice.")
                continue

            idx = int(choice_idx)

            if idx < 1 or idx > len(names):
                print("Invalid choice.")
                continue

            name = names[idx - 1]  # safe now

            times = get_schedule(name)
            print(f"\nSelected schedule: {name}")
            print("Times:", times)

            if times:
                print("Starting scheduler... (Ctrl+C to stop)\n")
                ringBell(times)
            else:
                print("This schedule has no times.")

        #Saved Schedules: IF WE ENTERS 0 ITS A BUG WHERE THE LAST Saved Schedu BELL WORKS (EVERY WHERE)
        # 3. Edit schedule (FIXED)
        elif choice == "3":
            names = list_schedule_names()
            if not names:
                print("No schedules to edit.")
                continue

            print("\nSchedules:")
            for i, n in enumerate(names):
                print(f"{i+1}. {n}")
            print("0. Back")

            choice_idx = input("Choose: ").strip()

            if choice_idx == "0":
                continue

            if not choice_idx.isdigit():
                print("Invalid choice.")
                continue

            idx = int(choice_idx)

            if idx < 1 or idx > len(names):
                print("Invalid choice.")
                continue

            name = names[idx - 1]

            print(f"\nEditing '{name}'")
            print("1. Rename schedule")
            print("2. Replace timings")
            sub = input("Choose: ").strip()

            if sub == "1":
                new_name = input("New name: ").strip()
                if new_name:
                    rename_schedule(name, new_name)
                    print("Renamed.")
                else:
                    print("Name cannot be empty.")

            elif sub == "2":
                print("Current times:", get_schedule(name))
                new_times = []
                print("Enter new times (type 'done' when finished).")
                while True:
                    t = input("Time: ").strip()
                    if t.lower() == "done":
                        break
                    try:
                        canonical = parse_time_to_24h(t)
                        new_times.append(canonical)
                    except Exception as e:
                        print("Invalid time:", e)
                update_schedule(name, new_times)
                print("Timings updated.")

            else:
                print("Invalid choice.")

        # 4. Create new schedule
        elif choice == "4":
            name = input("Schedule name: ").strip()
            if not name:
                print("Name cannot be empty.")
                continue

            times = []
            print("Enter times for this schedule (type 'done' when finished).")
            while True:
                t = input("Time: ").strip()
                if t.lower() == "done":
                    break
                try:
                    canonical = parse_time_to_24h(t)
                    times.append(canonical)
                except Exception as e:
                    print("Invalid time:", e)

            update_schedule(name, times)
            print(f"Schedule '{name}' created with times:", times)

        # 5. Delete schedule (FIXED)
        elif choice == "5":
            names = list_schedule_names()
            if not names:
                print("No schedules to delete.")
                continue

            print("\nSchedules:")
            for i, n in enumerate(names):
                print(f"{i+1}. {n}")
            print("0. Back")

            choice_idx = input("Choose: ").strip()

            if choice_idx == "0":
                continue

            if not choice_idx.isdigit():
                print("Invalid choice.")
                continue

            idx = int(choice_idx)

            if idx < 1 or idx > len(names):
                print("Invalid choice.")
                continue

            name = names[idx - 1]

            confirm = input(f"Delete schedule '{name}'? (y/n): ").strip().lower()
            if confirm == "y":
                delete_schedule(name)
                print("Deleted.")
            else:
                print("Cancelled.")
        elif choice == "0":
            set_mode("IDLE")
            return
        else:
            print("Invalid choice.\n")

# -------------------------------------------------------------
# Add this typewriter function
# ------------------------------------------------------------
def typewriter(text, delay=0.02):
    """Print characters one by one like typing."""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()
    
def load_about_us():
    try:
        with open("about_us.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "About Us file (about_us.txt) not found."





# -------------------------------------------------------------
# MAIN MENU
# -------------------------------------------------------------

def main_menu():
    while True:
        print("\n\t\tJOTHI - SMART BELL & ASSEMBLY SYSTEM")
        print("\n========== MAIN MENU ==========")
        print("1. Bell Mode")
        print("2. Assembly")
        print("3. Announcement")
        print("4. Settings")
        print("5. About Us")
        print("0. Exit")
        choice = input("Choose: ").strip()

        if choice == "1":
            bell_menu()

        elif choice == "2":
            assembly_menu()

        elif choice == "3":
            announcement_menu()

        elif choice == "4":
            settings_menu()

        elif choice == "5":
            print("\n========== ABOUT US ==========\n")
            about_text = load_about_us()
            typewriter(about_text, delay=0.01)
            print("\n==============================\n")
            input("Press Enter to go back.")

        elif choice == "0":
            print("Goodbye!")
            break

        else:
            print("Invalid option.\n")


# -------------------------------------------------------------
# RUN PROGRAM
# -------------------------------------------------------------

if __name__ == "__main__":
    main_menu()

