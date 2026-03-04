import asyncio
import os
import psycopg2
from flask import Flask, request
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Update, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandObject, Command

app = Flask(__name__)

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 5602492161 # Твой ID
DB_URL = os.getenv("DATABASE_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher()
admin_states = {}

# Инициализация таблицы при старте
def init_db():
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        referrer_id BIGINT,
                        refs_count INTEGER DEFAULT 0
                    );
                """)
                conn.commit()
    except Exception as e:
        print(f"Ошибка БД: {e}")

# --- КЛАВИАТУРЫ ---
def main_menu(user_id):
    kb = [
        [InlineKeyboardButton(text="🔗 Моя ссылка", callback_data="my_ref")],
        [InlineKeyboardButton(text="🏆 ТОП по никам", callback_data="show_top")]
    ]
    if user_id == ADMIN_ID:
        kb.append([InlineKeyboardButton(text="⚙️ Админка", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# --- ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def start(message: types.Message, command: CommandObject):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    first_name = message.from_user.first_name
    
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
            if not cur.fetchone():
                ref_id = int(command.args) if command.args and command.args.isdigit() else None
                cur.execute(
                    "INSERT INTO users (user_id, username, first_name, referrer_id) VALUES (%s, %s, %s, %s)",
                    (user_id, username, first_name, ref_id)
                )
                if ref_id:
                    cur.execute("UPDATE users SET refs_count = refs_count + 1 WHERE user_id = %s", (ref_id,))
                conn.commit()

    await message.answer("🚀 Привет! Бот работает на Postgres.", reply_markup=main_menu(user_id))

@dp.callback_query()
async def actions(call: types.CallbackQuery):
    user_id = call.from_user.id
    if call.data == "my_ref":
        me = await bot.get_me()
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT refs_count FROM users WHERE user_id = %s", (user_id,))
                res = cur.fetchone()
                count = res[0] if res else 0
        await call.message.answer(f"💎 Рефералов: {count}\n🔗 Ссылка: https://t.me/{me.username}?start={user_id}")
    
    elif call.data == "admin_panel":
        admin_states[ADMIN_ID] = "waiting"
        await call.message.answer("🛠 Режим рассылки включен. Отправь сообщение!")

@dp.message()
async def handle_all(message: types.Message):
    if message.from_user.id == ADMIN_ID and admin_states.get(ADMIN_ID) == "waiting":
        admin_states[ADMIN_ID] = None
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM users")
                users = cur.fetchall()
        for u in users:
            try: await message.copy_to(u[0])
            except: continue
        await message.answer("✅ Рассылка готова!")
    else:
        await message.answer("Используй кнопки меню.", reply_markup=main_menu(message.from_user.id))

# --- VERCEL ---
init_db()

async def process_event(update_dict):
    update = Update.model_validate(update_dict, context={"bot": bot})
    try: await dp.feed_update(bot, update)
    finally: await bot.session.close()

@app.route('/', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        asyncio.run(process_event(request.get_json()))
    return "OK", 200
