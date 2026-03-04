import asyncio
import os
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from aiogram.filters import Command

# Настройка Flask
app = Flask(__name__)

# Инициализация бота и диспетчера
TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Обработчик команды /start
@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer("🚀 Бот успешно запущен в Vercel!")

# Эхо-обработчик для проверки связи
@dp.message()
async def echo_handler(message: types.Message):
    await message.answer(f"🤖 Ты написал: {message.text}")

# Главный роут для Vercel
@app.route('/', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        # Получаем данные от Telegram
        update_data = request.get_json()
        update = Update.model_validate(update_data, context={"bot": bot})
        
        # Запускаем обработку события в текущем цикле
        asyncio.run(dp.feed_update(bot, update))
        return "OK", 200
    
    return "<h1>Bot is alive!</h1>", 200
