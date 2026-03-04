import asyncio
import os
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from aiogram.webhook.backend.flask import FlaskRequestHandler

# --- Конфигурация ---
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = Flask(__name__)

# --- Обработчик сообщений ---
@dp.message()
async def echo_handler(message: types.Message):
    # Используем простую отправку. В режиме вебхука aiogram сам поймет, как ответить.
    await message.answer(f"✅ Бот работает через Webhook!\nТвой ID: {message.from_user.id}")

# --- Настройка обработчика для Flask ---
# Это специальный класс от aiogram, который правильно связывает Flask и бота
handler = FlaskRequestHandler(dp, bot)

@app.route('/', methods=['POST'])
def webhook_handle():
    # Этот метод берет на себя всю сложную работу с asyncio и aiohttp
    return handler.handle(request)

# Для совместимости с Vercel
def main(environ, start_response):
    return app(environ, start_response)

# ВАЖНО: Для Vercel Python Runtime объект приложения должен называться 'app'
# и мы НЕ добавляем функцию handler(environ, start_response) вручную, 
# если используем Flask — Vercel сам его найдет.
