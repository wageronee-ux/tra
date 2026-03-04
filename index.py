import asyncio
import os
import psycopg2
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Update
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from flask import Flask, request

# ==========================================
# ⚙️ КОНФИГУРАЦИЯ (Берем из Vercel)
# ==========================================
# ==========================================
# ⚙️ КОНФИГУРАЦИЯ (Берем из Environment Variables)
# ==========================================
TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", 0))
CHANNEL_URL = os.getenv("CHANNEL_URL")
GIF_URL = "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExYzVjdWl6MnBrdnpza2FhOGRvbjcxMDQ2MzQyNGI5eHV4cGw1MmxpciZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/5zmRYubj7t6H1gxDY7/giphy.gif"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
app = Flask(__name__)

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_price = State()

# ==========================================
# 🗄️ БАЗА ДАННЫХ (PostgreSQL / Supabase)
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

# Функция для получения настроек
def get_setting(key):
    res = db_query("SELECT value FROM settings WHERE key=%s", (key,), True)
    return res[0][0] if res else 0.1

# ==========================================
# 🛠️ ФУНКЦИИ И КЛАВИАТУРЫ
# ==========================================
async def check_sub(user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except: return False

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

def admin_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Рассылка", callback_data="admin_broadcast")
    builder.button(text="💰 Цена рефа", callback_data="admin_set_price")
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

# ==========================================
# 🚀 ОБРАБОТЧИКИ
# ==========================================

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    fname = message.from_user.full_name
    uname = message.from_user.username or "NoUser"
    
    user = db_query("SELECT user_id FROM users WHERE user_id=%s", (user_id,), True)
    
    if not user:
        args = message.text.split()
        ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        db_query("INSERT INTO users (user_id, full_name, username, referred_by) VALUES (%s, %s, %s, %s)", 
                 (user_id, fname, uname, ref_id))
        
        if ref_id and ref_id != user_id:
            pay = get_setting('pay_per_ref')
            db_query("UPDATE users SET balance = balance + %s, referrals_count = referrals_count + 1 WHERE user_id = %s", (pay, ref_id))
            try: await bot.send_message(ref_id, f"🔔 +${pay} за друга!")
            except: pass
    
    if not await check_sub(user_id):
        kb = InlineKeyboardBuilder()
        kb.button(text="📢 Подписаться", url=CHANNEL_URL)
        kb.button(text="✅ Проверить", callback_data="check_sub_btn")
        return await message.answer_animation(animation=GIF_URL, caption="⚠️ Подпишись на канал!", reply_markup=kb.as_markup())

    await message.answer_animation(animation=GIF_URL, caption=f"🚀 Привет, {fname}!", reply_markup=main_kb(user_id))

@dp.callback_query(F.data == "check_sub_btn")
async def check_sub_cb(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.delete()
        await bot.send_animation(call.from_user.id, animation=GIF_URL, caption="✅ Доступ открыт!", reply_markup=main_kb(call.from_user.id))
    else:
        await call.answer("❌ Вы не подписаны!", show_alert=True)

# --- АДМИНКА ---
@dp.callback_query(F.data == "admin_panel", F.from_user.id == ADMIN_ID)
async def admin_p(call: types.CallbackQuery):
    users_count = db_query("SELECT COUNT(*) FROM users", fetch=True)[0][0]
    price = get_setting('pay_per_ref')
    await call.message.edit_caption(caption=f"⚙️ **АДМИН-ПАНЕЛЬ**\n\n👥 Юзеров: `{users_count}`\n💵 Оплата за рефа: `${price}`", reply_markup=admin_kb())

@dp.callback_query(F.data == "admin_set_price", F.from_user.id == ADMIN_ID)
async def set_price_step(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Введите новую цену за рефа (например 0.15):")
    await state.set_state(AdminStates.waiting_for_price)

@dp.message(AdminStates.waiting_for_price)
async def save_price(message: types.Message, state: FSMContext):
    try:
        new_val = float(message.text)
        db_query("UPDATE settings SET value = %s WHERE key = 'pay_per_ref'", (new_val,))
        await message.answer(f"✅ Установлено: ${new_val}")
        await state.clear()
    except: await message.answer("Введите число!")

@dp.callback_query(F.data == "admin_broadcast", F.from_user.id == ADMIN_ID)
async def broadcast_step(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Введите текст рассылки:")
    await state.set_state(AdminStates.waiting_for_broadcast)

@dp.message(AdminStates.waiting_for_broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    users = db_query("SELECT user_id FROM users", fetch=True)
    count = 0
    for (uid,) in users:
        try:
            await bot.send_message(uid, message.text)
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"✅ Рассылка завершена ({count} чел.)")
    await state.clear()

# --- ПРОФИЛЬ И ТОП ---
@dp.callback_query(F.data == "profile")
async def profile(call: types.CallbackQuery):
    res = db_query("SELECT balance, referrals_count FROM users WHERE user_id=%s", (call.from_user.id,), True)[0]
    await call.message.edit_caption(caption=f"👤 **ПРОФИЛЬ**\n\n💰 Баланс: `${res[0]:.2f}`\n👥 Рефералов: `{res[1]}`", reply_markup=main_kb(call.from_user.id))

@dp.callback_query(F.data == "top")
async def top_leaders(call: types.CallbackQuery):
    top = db_query("SELECT full_name, username, referrals_count FROM users ORDER BY referrals_count DESC LIMIT 10", fetch=True)
    text = "🏆 **ТОП 10**\n\n"
    for i, (name, uname, count) in enumerate(top, 1):
        link = f"[{name}](https://t.me/{uname})" if uname != "NoUser" else name
        text += f"{i}. {link} — {count} чел.\n"
    await call.message.edit_caption(caption=text, reply_markup=main_kb(call.from_user.id), parse_mode="Markdown")

@dp.callback_query(F.data == "ref_link")
async def ref_link(call: types.CallbackQuery):
    me = await bot.get_me()
    await call.message.edit_caption(caption=f"🔗 **Твоя ссылка:**\n`https://t.me/{me.username}?start={call.from_user.id}`", reply_markup=main_kb(call.from_user.id), parse_mode="Markdown")

@dp.callback_query(F.data == "withdraw")
async def withdraw(call: types.CallbackQuery):
    res = db_query("SELECT balance, full_name FROM users WHERE user_id=%s", (call.from_user.id,), True)[0]
    min_w = get_setting('min_withdraw')
    if res[0] < min_w:
        await call.answer(f"❌ Минимум ${min_w}", show_alert=True)
    else:
        await bot.send_message(LOG_CHANNEL_ID, f"💸 **ВЫВОД**\nЮзер: {res[1]}\nСумма: ${res[0]:.2f}")
        await call.answer("✅ Заявка отправлена!", show_alert=True)

@dp.callback_query(F.data == "back_to_main")
async def back(call: types.CallbackQuery):
    await call.message.edit_caption(caption="🚀 Главное меню", reply_markup=main_kb(call.from_user.id))

# ==========================================
# 🛠️ ОБРАБОТЧИК ДЛЯ VERCEL
# ==========================================
@app.route('/', methods=['POST'])
async def webhook():
    if request.method == 'POST':
        update = Update.model_validate(request.get_json(), context={"bot": bot})
        await dp.feed_update(bot, update)
        return "OK", 200
    return "Forbidden", 403

def handler(environ, start_response):
    return app(environ, start_response)
