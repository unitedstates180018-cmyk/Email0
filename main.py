import telebot
import requests
import random
import string
import re
import json
import os
import time
import threading
from flask import Flask

# ================= CONFIG =================

TOKEN = "8201558492:AAEXTj3oTVYVoXml4UonyWXssVDk0Ht27mQ"
ADMIN_ID = "7096192507"

BASE_URL = "https://api.mail.tm"
DATA_FILE = "data.json"

EXPIRY_TIME = 600
CHECK_INTERVAL = 5
FREE_LIMIT = 3

# =========================================

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)
START_TIME = time.time()

# ================= DATA ==================

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        user_data = json.load(f)
else:
    user_data = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(user_data, f)

# ================= DASHBOARD ==============

@app.route("/")
def dashboard():
    total_users = len(user_data)
    total_emails = sum(len(v["emails"]) for v in user_data.values())
    uptime = int(time.time() - START_TIME)

    return f"""
<html>
<head>
<meta http-equiv="refresh" content="5">
<style>
body {{background:#111;color:#fff;text-align:center;font-family:sans-serif}}
.box {{background:#222;margin:20px;padding:20px;border-radius:10px}}
</style>
</head>
<body>
<h1>🚀 Live Dashboard</h1>
<div class='box'>👥 Users: {total_users}</div>
<div class='box'>📧 Emails: {total_emails}</div>
<div class='box'>⏳ Uptime: {uptime} sec</div>
</body>
</html>
"""

def run_dashboard():
    app.run(host="0.0.0.0", port=5000)

threading.Thread(target=run_dashboard, daemon=True).start()

# ================= MAIL FUNCTIONS =========

def get_domain():
    try:
        r = requests.get(f"{BASE_URL}/domains")
        domains = r.json().get("hydra:member", [])
        if not domains:
            return None
        return random.choice(domains)["domain"]
    except:
        return None

def create_account():
    domain = get_domain()
    if not domain:
        return None, None

    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    email = f"{username}@{domain}"
    password = "Pass123456"

    requests.post(f"{BASE_URL}/accounts", json={
        "address": email,
        "password": password
    })

    return email, password

def get_token(email, password):
    try:
        r = requests.post(f"{BASE_URL}/token", json={
            "address": email,
            "password": password
        })
        return r.json().get("token")
    except:
        return None

def get_messages(token):
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/messages", headers=headers)
        return r.json().get("hydra:member", [])
    except:
        return []

def read_message(token, msg_id):
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/messages/{msg_id}", headers=headers)
        return r.json()
    except:
        return {}

def extract_otp(text):
    otp = re.findall(r'\b\d{4,8}\b', text)
    return otp[0] if otp else None

# ================= AUTO OTP ===============

def auto_otp_checker():
    while True:
        time.sleep(CHECK_INTERVAL)
        for user_id in list(user_data.keys()):
            for email_data in user_data[user_id]["emails"]:
                token = email_data["token"]
                last_id = email_data.get("last_msg_id")

                messages = get_messages(token)
                if not messages:
                    continue

                latest_id = messages[0]["id"]
                if latest_id == last_id:
                    continue

                msg = read_message(token, latest_id)
                body = msg.get("text", "") or msg.get("html", "")
                otp = extract_otp(body)

                if otp:
                    bot.send_message(
                        user_id,
                        f"🔔 <b>New OTP</b>\n📩 {email_data['email']}\n🔐 <code>{otp}</code>"
                    )

                email_data["last_msg_id"] = latest_id
                save_data()

threading.Thread(target=auto_otp_checker, daemon=True).start()

# ================= EXPIRY =================

def expiry_checker():
    while True:
        time.sleep(60)
        now = time.time()

        for user_id in list(user_data.keys()):
            for email in list(user_data[user_id]["emails"]):
                if now - email["created_at"] > EXPIRY_TIME:
                    user_data[user_id]["emails"].remove(email)
                    bot.send_message(
                        user_id,
                        f"⏰ Expired: {email['email']}"
                    )
        save_data()

threading.Thread(target=expiry_checker, daemon=True).start()

# ================= MENU ===================

def main_menu():
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("📩 Generate", callback_data="generate"),
        telebot.types.InlineKeyboardButton("📂 My Emails", callback_data="list")
    )
    return markup

# ================= START ==================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.chat.id)

    if user_id not in user_data:
        user_data[user_id] = {
            "premium": False,
            "emails": []
        }

    save_data()

    bot.send_message(
        user_id,
        "✨ <b>Premium Temp Mail Bot</b>",
        reply_markup=main_menu()
    )

# ================= ADMIN ==================

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    user_id = str(message.chat.id)

    if user_id != ADMIN_ID:
        bot.send_message(user_id, "⛔ Access Denied")
        return

    total_users = len(user_data)
    total_emails = sum(len(v["emails"]) for v in user_data.values())
    uptime = int(time.time() - START_TIME)

    bot.send_message(
        user_id,
        f"👑 Admin Panel\n\nUsers: {total_users}\nEmails: {total_emails}\nUptime: {uptime}s"
    )

# ================= CALLBACK ===============

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    user_id = str(call.message.chat.id)

    if call.data == "generate":

        if not user_data[user_id]["premium"] and \
        len(user_data[user_id]["emails"]) >= FREE_LIMIT:
            bot.send_message(user_id, "🚫 Free limit reached (3 emails).")
            return

        email, password = create_account()

        if not email:
            bot.send_message(user_id, "❌ Email creation failed")
            return

        token = get_token(email, password)
        if not token:
            bot.send_message(user_id, "❌ Token failed")
            return

        user_data[user_id]["emails"].append({
            "email": email,
            "token": token,
            "created_at": time.time(),
            "last_msg_id": None
        })

        save_data()

        bot.send_message(
            user_id,
            f"✅ Created:\n<code>{email}</code>",
            reply_markup=main_menu()
        )

    elif call.data == "list":

        if not user_data[user_id]["emails"]:
            bot.send_message(user_id, "📭 No emails")
            return

        for i, data in enumerate(user_data[user_id]["emails"]):
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(
                telebot.types.InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{i}"),
                telebot.types.InlineKeyboardButton("🗑 Delete", callback_data=f"delete_{i}")
            )

            bot.send_message(
                user_id,
                f"📩 <code>{data['email']}</code>",
                reply_markup=markup
            )

    elif call.data.startswith("delete_"):
        index = int(call.data.split("_")[1])
        deleted = user_data[user_id]["emails"].pop(index)
        save_data()
        bot.send_message(user_id, f"🗑 Deleted {deleted['email']}")

    elif call.data.startswith("refresh_"):
        index = int(call.data.split("_")[1])
        data = user_data[user_id]["emails"][index]

        messages = get_messages(data["token"])
        if not messages:
            bot.send_message(user_id, "📭 No messages")
            return

        msg = read_message(data["token"], messages[0]["id"])
        body = msg.get("text", "") or msg.get("html", "")
        otp = extract_otp(body) or "No OTP"

        bot.send_message(
            user_id,
            f"📩 {data['email']}\n🔐 <code>{otp}</code>"
        )

# ================= RUN ====================

print("Ultimate Bot Running...")
bot.infinity_polling()
