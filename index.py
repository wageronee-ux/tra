import asyncio
from flask import Flask, request, jsonify
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
import os

app = Flask(__name__)
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

# Твой обработчик
@dp.message()
async def handle_message(message: types.Message):
    await message.answer("Бот работает через Vercel! 🚀")

@app.route('/', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        update = Update.model_validate(request.get_json(), context={"bot": bot})
        # Запуск обработки
        asyncio.run(dp.feed_update(bot, update))
        return "OK", 200
    return "Bot is alive", 200

# Для Vercel обязательно
app = app
