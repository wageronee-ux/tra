import asyncio
import os
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from aiogram.filters import Command # Важно для работы /start

# Инициализация Flask
app = Flask(__name__)

# Инициализация бота (токен берется из переменных окружения Vercel)
TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- БЛОК ОБРАБОТЧИКОВ (ХЕНДЛЕРОВ) ---

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    """Реагирует на команду /start"""
    await message.answer("✅ Бот успешно распознал команду /start и работает на Vercel!")

@dp.message(Command("help"))
async def send_help(message: types.Message):
    """Реагирует на команду /help"""
    await message.answer("Я — бот на aiogram 3. Отправь мне любое сообщение!")

@dp.message()
async def echo_all(message: types.Message):
    """Ловит все остальные текстовые сообщения"""
    await message.answer(f"🤖 Получено сообщение: {message.text}")

# --- ЛОГИКА WEBHOOK (ДЛЯ VERCEL) ---

async def process_update(data):
    """Асинхронная подача данных в диспетчер aiogram"""
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)

@app.route('/', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        try:
            # Читаем данные от Telegram
            data = request.get_json()
            
            # В Serverless нужно создавать новый цикл событий для каждого запроса
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(process_update(data))
            loop.close()
            
            return "OK", 200
        except Exception as e:
            print(f"Error processing update: {e}")
            return "OK", 200 # Всегда 200, чтобы не зацикливать ошибки
    
    # Ответ для обычного перехода по ссылке в браузере
    return "<h1>Bot Status: Online</h1>", 200

# Экспортируем для Vercel
app = app
