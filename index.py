import asyncio
import os
import psycopg2
from flask import Flask, request, jsonify
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update

# --- Конфигурация ---
TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = Flask(__name__)

# --- Простейший обработчик ---
@dp.message()
async def echo_handler(message: types.Message):
    await message.answer(f"✅ Бот активен!\nID: {message.from_user.id}")

# --- Основной маршрут для Vercel ---
@app.route('/', methods=['POST', 'GET'])
def v_handler():
    if request.method == 'GET':
        return "Bot is running", 200
    
    # Обработка POST (Webhook)
    try:
        # Получаем данные от Telegram
        update_data = request.get_json()
        update = Update.model_validate(update_data, context={"bot": bot})
        
        # Запускаем асинхронную обработку в синхронном Flask
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(dp.feed_update(bot, update))
        finally:
            loop.close()
            
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

# Это имя переменной 'app' критически важно для Vercel
