import asyncio
import os
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext

# Инициализация Flask
app = Flask(__name__)

# Инициализация бота
bot = Bot(token=os.getenv("BOT_TOKEN"))
# В aiogram 3 хранилище указывается при создании диспетчера
dp = Dispatcher(storage=MemoryStorage())

# --- ХЕНДЛЕРЫ ---

# Убрали аргумент state="*", так как в 3.x он вызывает ошибку при таком использовании
@dp.message(Command("start"))
async def send_welcome(message: types.Message, state: FSMContext):
    """Реагирует на /start и сбрасывает любые зависшие состояния"""
    await state.clear() 
    await message.answer("✅ Теперь всё исправлено! Бот стабильно реагирует на /start.")

@dp.message(Command("help"))
async def send_help(message: types.Message):
    await message.answer("Если бот не отвечает, попробуй нажать /start")

@dp.message()
async def echo_all(message: types.Message):
    """Обрабатывает любой текст"""
    await message.answer(f"🤖 Получено: {message.text}")

# --- ЛОГИКА WEBHOOK ---

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
    return "<h1>Bot is online and fixed!</h1>", 200

app = app
