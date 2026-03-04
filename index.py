import asyncio
import os
import json
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update

# 1. Инициализация
app = Flask(__name__)
TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# 2. Твои обработчики
@dp.message()
async def handle_all_messages(message: types.Message):
    if message.text == "/start":
        await message.answer("🚀 Бот запущен! Отправь мне любое сообщение.")
    else:
        await message.answer(f"✅ Я получил твое сообщение: {message.text}")

# 3. Главная функция для Vercel
async def process_update(update_dict):
    update = Update.model_validate(update_dict, context={"bot": bot})
    await dp.feed_update(bot, update)

@app.route('/', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        try:
            update_dict = request.get_json()
            if update_dict:
                # Безопасный запуск асинхронного кода
                asyncio.run(process_update(update_dict))
            return "OK", 200
        except Exception as e:
            # Если ошибка в коде, мы все равно пишем OK, чтобы Telegram не спамил
            print(f"!!! Error: {e}")
            return "OK", 200
            
    return "Бот работает!", 200

# Заглушки для чистоты логов
@app.route('/favicon.ico')
@app.route('/favicon.png')
def favicon():
    return '', 204
