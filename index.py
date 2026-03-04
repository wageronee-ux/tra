import asyncio
import os
import psycopg2
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update

# --- Настройки ---
TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")
# Остальные переменные (ADMIN_ID и т.д.) подтянутся через os.getenv в хендлерах

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = Flask(__name__)

# --- База данных ---
def db_query(sql, params=(), fetch=False):
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute(sql, params)
    res = cur.fetchall() if fetch else None
    conn.commit()
    cur.close()
    conn.close()
    return res

# --- Базовый хендлер ---
@dp.message()
async def echo_handler(message: types.Message):
    await message.answer(f"Привет! Бот на связи. Твой ID: {message.from_user.id}")

# --- Webhook Route ---
@app.route('/', methods=['POST'])
def webhook():
    if request.method == 'POST':
        # Выполняем обработку апдейта синхронно для Flask
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        update = Update.model_validate(request.get_json(), context={"bot": bot})
        loop.run_until_complete(dp.feed_update(bot, update))
        return "OK", 200
    return "Forbidden", 403

# ВАЖНО: Для Vercel Python Runtime объект приложения должен называться 'app'
# и мы НЕ добавляем функцию handler(environ, start_response) вручную, 
# если используем Flask — Vercel сам его найдет.
