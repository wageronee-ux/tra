import asyncio
import os
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update

# Инициализация Flask
app = Flask(__name__)

# Инициализация бота. Токен должен быть добавлен в Vercel -> Settings -> Environment Variables
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

# --- ВАШИ ХЕНДЛЕРЫ ---

@dp.message(lambda message: message.text == "/start")
async def send_welcome(message: types.Message):
    await message.answer("🚀 Бот успешно запущен на Vercel!")

@dp.message()
async def echo_all(message: types.Message):
    """Хендлер-ловушка, чтобы все сообщения получали ответ и код 200"""
    await message.answer(f"Я получил твое сообщение: {message.text}")

# --- ЛОГИКА ОБРАБОТКИ WEBHOOK ---

async def process_update(data):
    """Функция для корректного запуска асинхронной обработки в Flask"""
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)

@app.route('/', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        try:
            # Получаем JSON от Telegram
            data = request.get_json()
            
            # Создаем новый цикл событий для обработки (важно для Serverless)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(process_update(data))
            loop.close()
            
            return "OK", 200
        except Exception as e:
            print(f"Error: {e}")
            # Возвращаем 200 даже при ошибке, чтобы Telegram не спамил повторами
            return "OK", 200
            
    return "<h1>Bot is running...</h1>", 200

# Для Vercel обязательно
app = app
