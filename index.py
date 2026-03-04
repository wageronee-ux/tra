import asyncio
import os
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update

# Инициализация Flask
app = Flask(__name__)

# Инициализация бота (токен берется из переменных окружения Vercel)
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

# --- ТВОИ ХЕНДЛЕРЫ ТУТ ---

@dp.message(lambda message: message.text == "/start")
async def send_welcome(message: types.Message):
    await message.answer("Привет! Я работаю на Vercel 🚀")

@dp.message()
async def echo_all(message: types.Message):
    # Этот хендлер ловит всё остальное, чтобы не было ошибок "not handled"
    await message.answer(f"Ты написал: {message.text}")

# --- ОБРАБОТКА WEBHOOK ---

@app.route('/', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        try:
            # Получаем данные от Telegram
            data = request.get_json()
            update = Update.model_validate(data, context={"bot": bot})
            
            # Запускаем обработку события
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(dp.feed_update(bot, update))
            
            return "OK", 200
        except Exception as e:
            print(f"Error processing update: {e}")
            return "OK", 200 # Возвращаем 200, чтобы остановить повторы от Telegram
    
    return "Bot is running...", 200

# Экспортируем app для Vercel
app = app
