import asyncio
import aiohttp
import aiosqlite
import random
import string
import re
import time

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8201558492:AAEXTj3oTVYVoXml4UonyWXssVDk0Ht27mQ"
ADMIN_ID = 7096192507
BASE_URL = "https://api.mail.tm"

FREE_LIMIT = 3

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# ================= DATABASE =================

async def init_db():
    async with aiosqlite.connect("database.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            premium INTEGER DEFAULT 0,
            premium_expiry INTEGER DEFAULT 0
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            email TEXT,
            token TEXT,
            created_at INTEGER
        )
        """)
        await db.commit()

# ================= PREMIUM CHECK =================

async def is_premium(user_id):
    async with aiosqlite.connect("database.db") as db:
        async with db.execute(
            "SELECT premium,premium_expiry FROM users WHERE user_id=?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()

    if not row:
        return False

    premium, expiry = row
    return premium == 1 and expiry > int(time.time())

# ================= MAIL SYSTEM =================

async def get_domain():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/domains") as r:
            data = await r.json()
            domains = data.get("hydra:member", [])
            if not domains:
                return None
            return random.choice(domains)["domain"]

async def create_account():
    domain = await get_domain()
    if not domain:
        return None, None

    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    email = f"{username}@{domain}"
    password = "Pass123456"

    async with aiohttp.ClientSession() as session:
        await session.post(f"{BASE_URL}/accounts", json={
            "address": email,
            "password": password
        })

    return email, password

async def get_token(email, password):
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{BASE_URL}/token", json={
            "address": email,
            "password": password
        }) as r:
            data = await r.json()
            return data.get("token")

# ================= MENU =================

def main_menu():
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("📩 Generate", callback_data="generate")
    )
    kb.add(
        InlineKeyboardButton("💎 Buy Premium", callback_data="buy")
    )
    return kb

# ================= START =================

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    async with aiosqlite.connect("database.db") as db:
        await db.execute(
            "INSERT OR IGNORE INTO users(user_id) VALUES(?)",
            (message.from_user.id,)
        )
        await db.commit()

    await message.answer(
        "🚀 <b>Pro Temp Mail Bot</b>\n\nFree Limit: 3 Emails\nPremium: Unlimited",
        reply_markup=main_menu()
    )

# ================= GENERATE =================

@dp.callback_query_handler(lambda c: c.data == "generate")
async def generate_handler(call: types.CallbackQuery):
    user_id = call.from_user.id
    premium = await is_premium(user_id)

    async with aiosqlite.connect("database.db") as db:
        async with db.execute(
            "SELECT COUNT(*) FROM emails WHERE user_id=?",
            (user_id,)
        ) as cur:
            count = (await cur.fetchone())[0]

    if not premium and count >= FREE_LIMIT:
        await call.message.answer(
            "🚫 Free limit reached (3 emails).\nUpgrade to Premium for Unlimited."
        )
        return

    email, password = await create_account()
    token = await get_token(email, password)

    async with aiosqlite.connect("database.db") as db:
        await db.execute(
            "INSERT INTO emails(user_id,email,token,created_at) VALUES(?,?,?,?)",
            (user_id, email, token, int(time.time()))
        )
        await db.commit()

    await call.message.answer(f"✅ Created:\n<code>{email}</code>")

# ================= BUY PREMIUM (INDIA) =================

@dp.callback_query_handler(lambda c: c.data == "buy")
async def buy_handler(call: types.CallbackQuery):
    text = """
💎 <b>Premium Plans (India)</b>

7 Days  - ₹99
30 Days - ₹299
90 Days - ₹699

💳 Payment Methods:

🔹 UPI ID: yourupi@oksbi
🔹 Google Pay
🔹 PhonePe
🔹 Paytm

After payment send screenshot to admin.

⚡ Premium = Unlimited Emails
"""
    await call.message.answer(text)

# ================= ADMIN APPROVE =================

@dp.message_handler(commands=["approve"])
async def approve_handler(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        user_id = int(message.text.split()[1])
        days = int(message.text.split()[2])
    except:
        await message.reply("Usage: /approve user_id days")
        return

    expiry = int(time.time()) + days * 86400

    async with aiosqlite.connect("database.db") as db:
        await db.execute(
            "UPDATE users SET premium=1,premium_expiry=? WHERE user_id=?",
            (expiry, user_id)
        )
        await db.commit()

    await bot.send_message(
        user_id,
        f"🎉 Premium Activated for {days} days!"
    )

# ================= RUN =================

async def on_startup(dp):
    await init_db()

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup)
