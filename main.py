import telebot
import requests
import random
import string
import re
import time

TOKEN = "8201558492:AAEtDnfqwhmKc4NwZq0C2KiX3ElPtg0i4ag"
bot = telebot.TeleBot(TOKEN)

user_data = {}

BASE_URL = "https://api.mail.tm"

def get_domain():
    r = requests.get(f"{BASE_URL}/domains")
    return r.json()["hydra:member"][0]["domain"]

def create_account():
    domain = get_domain()
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    email = f"{username}@{domain}"
    password = "Pass123456"
    
    data = {
        "address": email,
        "password": password
    }
    requests.post(f"{BASE_URL}/accounts", json=data)
    return email, password

def get_token(email, password):
    data = {
        "address": email,
        "password": password
    }
    r = requests.post(f"{BASE_URL}/token", json=data)
    return r.json()["token"]

def get_messages(token):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE_URL}/messages", headers=headers)
    return r.json()["hydra:member"]

def read_message(token, msg_id):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE_URL}/messages/{msg_id}", headers=headers)
    return r.json()

def extract_otp(text):
    otp = re.findall(r'\b\d{4,8}\b', text)
    return otp[0] if otp else "No OTP Found"

@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("📧 Generate Email", callback_data="generate"),
        telebot.types.InlineKeyboardButton("📂 My Emails", callback_data="list")
    )
    bot.send_message(message.chat.id, "🔥 Professional Temp Mail Bot", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    user_id = call.message.chat.id

    if call.data == "generate":
        email, password = create_account()
        token = get_token(email, password)

        if user_id not in user_data:
            user_data[user_id] = []

        user_data[user_id].append({
            "email": email,
            "password": password,
            "token": token
        })

        bot.send_message(user_id, f"✅ New Email:\n`{email}`", parse_mode="Markdown")

    elif call.data == "list":
        if user_id not in user_data or not user_data[user_id]:
            bot.send_message(user_id, "❌ No emails found.")
            return

        markup = telebot.types.InlineKeyboardMarkup()
        for i, data in enumerate(user_data[user_id]):
            markup.add(
                telebot.types.InlineKeyboardButton(
                    f"📩 {data['email']}",
                    callback_data=f"check_{i}"
                )
            )

        bot.send_message(user_id, "📂 Your Emails:", reply_markup=markup)

    elif call.data.startswith("check_"):
        index = int(call.data.split("_")[1])
        data = user_data[user_id][index]
        messages = get_messages(data["token"])

        if not messages:
            bot.send_message(user_id, "📭 No messages yet.")
            return

        msg = read_message(data["token"], messages[0]["id"])
        otp = extract_otp(msg.get("text", ""))

        bot.send_message(user_id,
                         f"📧 {data['email']}\n\n"
                         f"📩 Subject: {msg.get('subject')}\n\n"
                         f"🔐 OTP: {otp}")

bot.polling()
