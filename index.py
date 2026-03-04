import asyncio
import os
import psycopg2
from flask import Flask, request
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Update
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.webhook.backend.flask import FlaskRequestHandler

# ==========================================
# ⚙️ КОНФИГУРАЦИЯ
# ==========================================
TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", 0))
CHANNEL_URL = os.getenv("CHANNEL_URL")
GIF_URL = "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExYzVjdWl6MnBrdnpza2FhOGRvbjcxMDQ2MzQyNGI5eHV4cGw1MmxpciZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/5zmRYubj7t6H1gxDY7/giphy.gif"

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = Flask(__name__)

# ==========================================
# 🗄️ БАЗА ДАННЫХ
# ==========================================
def db_query(sql, params=(), fetch=False):
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute(sql, params)
    res = cur.fetchall() if fetch else None
    conn.commit()
    cur.close()
    conn.close()
    return res

def get_setting(key):
    res = db_query("SELECT value FROM settings WHERE key=%s", (key,), True)
    return res[0][0] if res else 0.1

# ==========================================
# 🛠️ КЛАВИАТУРЫ
# ==========================================
def main_kb(user_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Профиль", callback_data="profile")
    builder.button(text="🔗 Ссылка", callback_data="ref_link")
    builder.button(text="🏆 ТОП 10", callback_data="top")
    builder.button(text="💸 Вывод", callback_data="withdraw")
    if user_id == ADMIN_ID:
        builder.button(text="⚙️ Админ-панель", callback_data="admin_panel")
    builder.adjust(2)
    return builder.as_markup()

# ==========================================
# 🚀 ОБРАБОТЧИКИ (HANDLERS)
# ==========================================

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    user = db_query("SELECT user_id FROM users WHERE user_id=%s", (user_id,), True)
    
    if not user:
        args = message.text.split()
        ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        db_query("INSERT INTO users (user_id, full_name, username, referred_by) VALUES (%s, %s, %s, %s)", 
                 (user_id, message.from_user.full_name, message.from_user.username, ref_id))
        if ref_id and ref_id != user_id:
            pay = get_setting('pay_per_ref')
            db_query("UPDATE users SET balance = balance + %s, referrals_count = referrals_count + 1 WHERE user_id = %s", (pay, ref_id))

    await message.answer_animation(animation=GIF_URL, caption=f"🚀 Привет!", reply_markup=main_kb(user_id))

@dp.callback_query(F.data == "profile")
async def profile_cb(call: types.CallbackQuery):
    res = db_query("SELECT balance, referrals_count FROM users WHERE user_id=%s", (call.from_user.id,), True)[0]
    await call.message.edit_caption(caption=f"👤 **ПРОФИЛЬ**\n\n💰 Баланс: `${res[0]:.2f}`\n👥 Рефералов: `{res[1]}`", reply_markup=main_kb(call.from_user.id))

@dp.callback_query(F.data == "ref_link")
async def ref_link_cb(call: types.CallbackQuery):
    me = await bot.get_me()
    await call.message.edit_caption(caption=f"🔗 **Твоя ссылка:**\n`https://t.me/{me.username}?start={call.from_user.id}`", reply_markup=main_kb(call.from_user.id))

# ==========================================
# 🛠️ ВЕБХУК КОНФИГ
# ==========================================
handler = FlaskRequestHandler(dp, bot)

@app.route('/', methods=['POST'])
def webhook():
    return handler.handle(request)

# Обработка GET для проверки работоспособности
@app.route('/', methods=['GET'])
def index():
    return "Bot is running!", 200
