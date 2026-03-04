import asyncio
import os
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from aiogram.filters import Command

# 1. Настройка Flask (чтобы Vercel видел веб-сервер)
app = Flask(__name__)

# 2. Инициализация бота (токен берется из переменных окружения Vercel)
TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ТВОИ ОБРАБОТЧИКИ ТУТ ---

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("✅ Бот запущен и работает на Vercel!")

@dp.message()
async def echo_handler(message: types.Message):
    # Бот будет просто повторять текст, чтобы ты видел, что он живой
    await message.answer(f"🤖 Получил: {message.text}")

# --- ЛОГИКА ДЛЯ VERCEL ---

@app.route('/', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        update_dict = request.get_json()
        if update_dict:
            update = Update.model_validate(update_dict, context={"bot": bot})
            # Запускаем обработку события
            asyncio.run(dp.feed_update(bot, update))
        return "OK", 200
    return "Бот работает!", 200

# Заглушка, чтобы в логах не было ошибок 404 (favicon)
@app.route('/favicon.ico')
def favicon():
    return '', 204
