import asyncio
import aiohttp
import aiosqlite
import random
import string
import re
import time

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

TOKEN = "8201558492:AAEXTj3oTVYVoXml4UonyWXssVDk0Ht27mQ"
ADMIN_ID = 7096192507
BASE_URL = "https://api.mail.tm"

FREE_LIMIT = 3
FREE_EXPIRY = 600

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher()

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
            created_at INTEGER,
            last_msg_id TEXT
        )
        """)
        await db.commit()

# ================= MAIL =================

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

def extract_otp(text):
    otp = re.findall(r'\b\d{4,8}\b', text)
    return otp[0] if otp else None

# ================= PREMIUM CHECK =================

async def is_premium(user_id):
    async with aiosqlite.connect("database.db") as db:
        async with db.execute("SELECT premium,premium_expiry FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()

    if not row:
        return False

    premium, expiry = row
    return premium == 1 and expiry > int(time.time())

# ================= MENU =================

def main_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📩 Generate", callback_data="generate"),
            InlineKeyboardButton(text="📂 My Emails", callback_data="list")
        ],
        [
            InlineKeyboardButton(text="💎 Buy Premium", callback_data="buy")
        ]
    ])
    return kb

# ================= START =================

@dp.message(Command("start"))
async def start_handler(msg: Message):
    async with aiosqlite.connect("database.db") as db:
        await db.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (msg.from_user.id,))
        await db.commit()

    await msg.answer("🚀 <b>Pro Temp Mail Bot</b>", reply_markup=main_menu())

# ================= GENERATE =================

@dp.callback_query(F.data == "generate")
async def generate_handler(call: CallbackQuery):
    user_id = call.from_user.id
    premium = await is_premium(user_id)

    async with aiosqlite.connect("database.db") as db:
        async with db.execute("SELECT COUNT(*) FROM emails WHERE user_id=?", (user_id,)) as cur:
            count = (await cur.fetchone())[0]

    if not premium and count >= FREE_LIMIT:
        await call.message.answer("🚫 Free limit reached (3 emails)")
        return

    email, password = await create_account()
    token = await get_token(email, password)

    async with aiosqlite.connect("database.db") as db:
        await db.execute("""
        INSERT INTO emails(user_id,email,token,created_at)
        VALUES(?,?,?,?)
        """, (user_id, email, token, int(time.time())))
        await db.commit()

    await call.message.answer(f"✅ Created:\n<code>{email}</code>")

# ================= BUY =================

@dp.callback_query(F.data == "buy")
async def buy_handler(call: CallbackQuery):
    text = """
💎 <b>Premium Plans</b>

7 Days - 99৳
30 Days - 299৳

Send payment to:
bKash: 01XXXXXXXXX

After payment send screenshot to admin.
"""
    await call.message.answer(text)

# ================= ADMIN APPROVE =================

@dp.message(Command("approve"))
async def approve_handler(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return

    try:
        user_id = int(msg.text.split()[1])
        days = int(msg.text.split()[2])
    except:
        await msg.reply("Usage: /approve user_id days")
        return

    expiry = int(time.time()) + days * 86400

    async with aiosqlite.connect("database.db") as db:
        await db.execute("""
        UPDATE users SET premium=1,premium_expiry=? WHERE user_id=?
        """, (expiry, user_id))
        await db.commit()

    await bot.send_message(user_id, f"🎉 Premium Activated for {days} days!")

# ================= OTP CHECKER =================

async def otp_checker():
    while True:
        await asyncio.sleep(3)

# ================= RUN =================

async def main():
    await init_db()
    asyncio.create_task(otp_checker())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
