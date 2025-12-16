"""
Simple WhatsApp webhook server for JOTHI School Bell System.
Save as whatsapp_server.py and run: python whatsapp_server.py
Requires: flask, requests
"""

import os
import json
import requests
from flask import Flask, request

# -------------------------
# Configuration - edit these (or set env vars)
# -------------------------
VERIFY_TOKEN = os.getenv("JOTHI_VERIFY_TOKEN", "JOTHI_VERIFY")
PHONE_NUMBER_ID = os.getenv("JOTHI_PHONE_NUMBER_ID", "YOUR_PHONE_NUMBER_ID")
ACCESS_TOKEN = os.getenv("JOTHI_ACCESS_TOKEN", "YOUR_WHATSAPP_TOKEN")

# Whitelisted admin numbers (E.164 format). Only these can control the bot.
# Edit these or load from file in your real app.
AUTHORIZED_USERS = {
    "+919876543210": "admin",   # example: principal
    "+919812345678": "staff",   # example: staff
    # add yourself, e.g. "+91XXXXXXXXXX": "developer"
}


def is_authorized(number: str) -> bool:
    """Return True if sender is authorized to control the bot."""
    return number in AUTHORIZED_USERS


def get_role(number: str):
    return AUTHORIZED_USERS.get(number)


# -------------------------
# Flask app
# -------------------------
app = Flask(__name__)


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """
    Used by Meta during webhook registration.
    URL will be called with hub.mode, hub.verify_token, hub.challenge
    """
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("[Webhook] Verification successful")
        return challenge, 200
    else:
        return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def handle_webhook():
    """
    This receives incoming message events from Meta.
    We'll parse the JSON and handle text messages or audio attachment URLs.
    """
    data = request.get_json(force=True)
    print("[Webhook] Incoming payload:", json.dumps(data)[:1000])  # trim long logs

    # WhatsApp messages generally arrive under entry -> changes -> value -> messages
    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages")
                if not messages:
                    continue
                for msg in messages:
                    # call processing function (keeps this simple & synchronous)
                    process_whatsapp_message(msg, value)
    except Exception as e:
        print("Error processing webhook:", e)

    return "EVENT_RECEIVED", 200


# -------------------------
# Processing incoming messages
# -------------------------
def process_whatsapp_message(msg: dict, value: dict):
    """
    msg example (text):
      { "from": "917xxxxxxxxx", "id":"...", "timestamp":"...", "text": {"body":"hello"} }
    audio example:
      { "type":"audio", "audio":{"mime_type":"audio/ogg","id":"..."} }
    """
    sender = msg.get("from")  # sender phone number (usually without +)
    if not sender:
        print("[msg] No sender found in message")
        return

    wa_number = sender if sender.startswith("+") else "+" + sender
    role = get_role(wa_number)
    print(f"[msg] from={wa_number} id={msg.get('id')} type={msg.get('type')} role={role}")

    # Authorization check
    if not is_authorized(wa_number):
        # polite rejection
        send_whatsapp_text(wa_number, "You are not authorized to use this bot.")
        print("[auth] unauthorized:", wa_number)
        return

    # Text message
    if msg.get("type") == "text":
        text = msg.get("text", {}).get("body", "")
        print("[text]", text)
        reply = handle_command(text.strip(), wa_number)
        if reply:
            send_whatsapp_text(wa_number, reply)
        return

    # Audio message (voice note)
    if msg.get("type") == "audio":
        media_id = msg.get("audio", {}).get("id")
        if media_id:
            print("[audio] received media id:", media_id)
            media_url, mime_type = get_media_url(media_id)
            if media_url:
                path = download_media_file(media_url, media_id, mime_type)
                # TODO: play or forward the file to your announcement engine
                send_whatsapp_text(wa_number, "Voice received and saved.")
            else:
                send_whatsapp_text(wa_number, "Failed to download audio.")
        else:
            send_whatsapp_text(wa_number, "No media id found in audio.")
        return

    # Other types
    send_whatsapp_text(wa_number, "Message type not supported yet.")


# -------------------------
# WhatsApp Cloud API helpers
# -------------------------
def send_whatsapp_text(to_number: str, text: str):
    """
    Send a simple text message back to the user.
    to_number must be in E.164 format like +9198xxxxxxx
    """
    global ACCESS_TOKEN, PHONE_NUMBER_ID
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID or "YOUR_WHATSAPP_TOKEN" in ACCESS_TOKEN or "YOUR_PHONE_NUMBER_ID" in PHONE_NUMBER_ID:
        print("[send] missing ACCESS_TOKEN or PHONE_NUMBER_ID - replace before real use")
        return False

    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number.lstrip("+"),
        "type": "text",
        "text": {"body": text}
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        print("[send] status", r.status_code, r.text)
        return r.ok
    except Exception as e:
        print("[send] exception:", e)
        return False


def get_media_url(media_id: str):
    """
    Request the media download URL from Meta for the given media_id.
    Returns (url, mime_type) or (None, None) on failure.
    """
    global ACCESS_TOKEN
    if not ACCESS_TOKEN or "YOUR_WHATSAPP_TOKEN" in ACCESS_TOKEN:
        print("[media] missing ACCESS_TOKEN")
        return None, None
    meta_url = f"https://graph.facebook.com/v20.0/{media_id}"
    params = {"fields": "url,mime_type"}
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    r = requests.get(meta_url, headers=headers, params=params, timeout=10)
    if r.status_code == 200:
        j = r.json()
        return j.get("url"), j.get("mime_type")
    print("[media] failed to get URL:", r.status_code, r.text)
    return None, None


def download_media_file(url: str, media_id: str, mime_type: str):
    """
    Download binary media to disk and return local path.
    """
    global ACCESS_TOKEN
    if not ACCESS_TOKEN or "YOUR_WHATSAPP_TOKEN" in ACCESS_TOKEN:
        print("[media] missing ACCESS_TOKEN")
        return None
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    try:
        r = requests.get(url, headers=headers, stream=True, timeout=20)
        if r.status_code == 200:
            ext = ".ogg" if "ogg" in mime_type else ".mp3" if "mpeg" in mime_type else ".bin"
            out = f"media_{media_id}{ext}"
            with open(out, "wb") as f:
                for chunk in r.iter_content(chunk_size=4096):
                    if chunk:
                        f.write(chunk)
            print("[media] downloaded to", out)
            return out
        else:
            print("[media] download failed", r.status_code, r.text)
    except Exception as e:
        print("[media] exception:", e)
    return None


# -------------------------
# Command handler (simple)
# -------------------------
# Note: adapt these commands to integrate with your bell system
def handle_command(text: str, sender: str) -> str:
    lower = text.lower().strip()
    if lower in ("/help", "help"):
        return (
            "JOTHI Bot commands:\n"
            "/help - show this message\n"
            "/announce <text> - announce (via offline voice)\n"
            "/schedule list - list saved schedules\n"
            "/about - about JOTHI"
        )

    if lower.startswith("/announce "):
        msg = text[len("/announce "):].strip()
        print("[announce] from", sender, " -> ", msg)
        # hook to your announcement function here
        return "Announcement played."

    if lower.startswith("/schedule"):
        cmd = lower.split()
        if len(cmd) >= 2 and cmd[1] == "list":
            # placeholder - replace with real schedules
            return "Saved schedules: Regular Day"
        return "Unknown schedule command."

    if lower == "/about" or lower == "about":
        return "JOTHI Bot - School Bell System"

    return "Unknown command. Type /help for commands."


# -------------------------
# Run server
# -------------------------
if __name__ == "__main__":
    print("Starting webhook server on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
