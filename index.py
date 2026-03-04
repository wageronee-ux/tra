import asyncio
import os
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update

app = Flask(__name__)
TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Обработчик сообщений
@dp.message()
async def handle_any_event(message: types.Message):
    try:
        await message.answer(f"✅ Стабильная связь! Ты написал: {message.text}")
    except Exception as e:
        print(f"Ошибка отправки: {e}")

# Функция для Vercel с правильным управлением циклом
async def main_process(update_dict):
    update = Update.model_validate(update_dict, context={"bot": bot})
    # Используем feed_update, но следим за сессией бота
    try:
        await dp.feed_update(bot, update)
    finally:
        # Важно закрыть сессию, чтобы Vercel не "подвешивал" процесс
        await bot.session.close()

@app.route('/', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        update_dict = request.get_json()
        if update_dict:
            # Запускаем один конкретный апдейт и закрываем его
            asyncio.run(main_process(update_dict))
        return "OK", 200
    return "Бот готов к работе!", 200

@app.route('/favicon.ico')
def favicon():
    return '', 204
