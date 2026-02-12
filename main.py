import telebot
import requests
import random
import string
import re

TOKEN = "8201558492:AAEtDnfqwhmKc4NwZq0C2KiX3ElPtg0i4ag"
bot = telebot.TeleBot(TOKEN)

user_emails = {}

def generate_email():
    name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    domain = "1secmail.com"
    return name, domain, f"{name}@{domain}"

def get_messages(login, domain):
    url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}"
    return requests.get(url).json()

def read_message(login, domain, msg_id):
    url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={msg_id}"
    return requests.get(url).json()

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
    bot.send_message(message.chat.id, "🔥 Multi Email Temp Mail Bot", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    user_id = call.message.chat.id

    if call.data == "generate":
        login, domain, email = generate_email()

        if user_id not in user_emails:
            user_emails[user_id] = []

        user_emails[user_id].append((login, domain, email))
        bot.send_message(user_id, f"✅ New Email:\n`{email}`", parse_mode="Markdown")

    elif call.data == "list":
        if user_id not in user_emails or not user_emails[user_id]:
            bot.send_message(user_id, "❌ No emails found.")
            return

        markup = telebot.types.InlineKeyboardMarkup()
        for index, (_, _, email) in enumerate(user_emails[user_id]):
            markup.add(
                telebot.types.InlineKeyboardButton(
                    f"📩 {email}",
                    callback_data=f"check_{index}"
                )
            )

        bot.send_message(user_id, "📂 Your Emails:", reply_markup=markup)

    elif call.data.startswith("check_"):
        index = int(call.data.split("_")[1])
        login, domain, email = user_emails[user_id][index]

        messages = get_messages(login, domain)

        if not messages:
            bot.send_message(user_id, "📭 No messages yet.")
            return

        msg = read_message(login, domain, messages[0]['id'])
        otp = extract_otp(msg['textBody'])

        bot.send_message(user_id,
                         f"📧 {email}\n\n"
                         f"📩 Subject: {msg['subject']}\n\n"
                         f"🔐 OTP: {otp}")

bot.polling()