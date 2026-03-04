import asyncio
import os
from flask import Flask, request
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Update
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext

app = Flask(__name__)

# Используем MemoryStorage для временного хранения состояний
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher(storage=MemoryStorage())

# --- ХЕНДЛЕРЫ ---

# state="*" позволяет команде работать, даже если бот ждет ответа на другой вопрос
@dp.message(Command("start"), state="*")
async def send_welcome(message: types.Message, state: FSMContext):
    """Сбрасывает любое состояние и приветствует пользователя"""
    await state.clear() # Очищаем состояние
    await message.answer("✅ Команда /start распознана! Я готов к работе.")

@dp.message(Command("help"))
async def send_help(message: types.Message):
    await message.answer("Отправь /start, если я перестал отвечать.")

@dp.message()
async def echo_all(message: types.Message):
    """Ловушка для любого текста"""
    await message.answer(f"🤖 Ты написал: {message.text}")

# --- ЛОГИКА VERCEL ---

async def process_update(data):
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)

@app.route('/', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        try:
            data = request.get_json()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(process_update(data))
            loop.close()
            return "OK", 200
        except Exception as e:
            print(f"Error: {e}")
            return "OK", 200
    return "<h1>Bot is online</h1>", 200

app = app
