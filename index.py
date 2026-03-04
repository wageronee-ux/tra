import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ==========================================
# ⚙️ КОНФИГУРАЦИЯ (ОБЯЗАТЕЛЬНО ЗАПОЛНИ)
# ==========================================
TOKEN = "8769684238:AAGAuYyLQCmWu0xx5hBZiQfSyqA6PLSSv1Q"
ADMIN_ID = 8040642138              # Твой ID (узнай в @userinfobot)
CHANNEL_ID = -1003851402932      # ID канала для подписки (с -100)
LOG_CHANNEL_ID = -1003850107854  # ID канала для логов (админка)
CHANNEL_URL = "https://t.me/traffchanel" # Ссылка на канал (без @)
GIF_URL = "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExYzVjdWl6MnBrdnpza2FhOGRvbjcxMDQ2MzQyNGI5eHV4cGw1MmxpciZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/5zmRYubj7t6H1gxDY7/giphy.gif"

bot = Bot(token=TOKEN)
dp = Dispatcher()

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_price = State()

# ==========================================
# 🗄️ БАЗА ДАННЫХ
# ==========================================
def db_query(sql, params=(), fetch=False):
    with sqlite3.connect("referral_bot.db") as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        res = cur.fetchall() if fetch else None
        conn.commit()
        return res

db_query('''CREATE TABLE IF NOT EXISTS users 
            (user_id INTEGER PRIMARY KEY, full_name TEXT, username TEXT,
             balance REAL DEFAULT 0, referred_by INTEGER, referrals_count INTEGER DEFAULT 0)''')

db_query('''CREATE TABLE IF NOT EXISTS settings 
            (key TEXT PRIMARY KEY, value REAL)''')

if not db_query("SELECT * FROM settings", fetch=True):
    db_query("INSERT INTO settings VALUES ('pay_per_ref', 0.1), ('min_withdraw', 5.0)")

def get_setting(key):
    res = db_query("SELECT value FROM settings WHERE key=?", (key,), True)
    return res[0][0] if res else 0.1

# ==========================================
# 🛠️ ФУНКЦИИ
# ==========================================
async def check_sub(user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except: return False

async def smart_edit(call, text, reply_markup):
    try:
        if call.message.animation or call.message.photo:
            await call.message.edit_caption(caption=text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await call.message.edit_text(text=text, reply_markup=reply_markup, parse_mode="Markdown")
    except:
        await call.message.answer(text, reply_markup=reply_markup, parse_mode="Markdown")

# ==========================================
# ⌨️ КЛАВИАТУРЫ
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
    fname, uname = message.from_user.full_name, message.from_user.username or "NoUser"
    user = db_query("SELECT user_id FROM users WHERE user_id=?", (user_id,), True)
    
    if not user:
        args = message.text.split()
        ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        db_query("INSERT INTO users (user_id, full_name, username, referred_by) VALUES (?, ?, ?, ?)", (user_id, fname, uname, ref_id))
        if ref_id and ref_id != user_id:
            pay = get_setting('pay_per_ref')
            db_query("UPDATE users SET balance = balance + ?, referrals_count = referrals_count + 1 WHERE user_id = ?", (pay, ref_id))
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

@dp.callback_query(F.data == "admin_panel", F.from_user.id == ADMIN_ID)
async def admin_p(call: types.CallbackQuery):
    users_count = db_query("SELECT COUNT(*) FROM users", fetch=True)[0][0]
    price = get_setting('pay_per_ref')
    text = f"⚙️ **АДМИН-ПАНЕЛЬ**\n\n👥 Юзеров: `{users_count}`\n💵 Оплата за рефа: `${price}`"
    await smart_edit(call, text, admin_kb())

@dp.callback_query(F.data == "admin_set_price", F.from_user.id == ADMIN_ID)
async def set_price_step(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Введите новую цену за рефа (например 0.15):")
    await state.set_state(AdminStates.waiting_for_price)

@dp.message(AdminStates.waiting_for_price)
async def save_price(message: types.Message, state: FSMContext):
    try:
        new_val = float(message.text)
        db_query("UPDATE settings SET value = ? WHERE key = 'pay_per_ref'", (new_val,))
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

@dp.callback_query(F.data == "profile")
async def profile(call: types.CallbackQuery):
    res = db_query("SELECT balance, referrals_count FROM users WHERE user_id=?", (call.from_user.id,), True)[0]
    await smart_edit(call, f"👤 **ПРОФИЛЬ**\n\n💰 Баланс: `${res[0]:.2f}`\n👥 Рефералов: `{res[1]}`", main_kb(call.from_user.id))

@dp.callback_query(F.data == "top")
async def top_leaders(call: types.CallbackQuery):
    top = db_query("SELECT full_name, username, referrals_count FROM users ORDER BY referrals_count DESC LIMIT 10", fetch=True)
    text = "🏆 **ТОП 10**\n\n"
    for i, (name, uname, count) in enumerate(top, 1):
        link = f"[{name}](https://t.me/{uname})" if uname != "NoUser" else name
        text += f"{i}. {link} — {count} чел.\n"
    await smart_edit(call, text, main_kb(call.from_user.id))

@dp.callback_query(F.data == "ref_link")
async def ref_link(call: types.CallbackQuery):
    me = await bot.get_me()
    await smart_edit(call, f"🔗 **Твоя ссылка:**\n`https://t.me/{me.username}?start={call.from_user.id}`", main_kb(call.from_user.id))

@dp.callback_query(F.data == "withdraw")
async def withdraw(call: types.CallbackQuery):
    res = db_query("SELECT balance, full_name FROM users WHERE user_id=?", (call.from_user.id,), True)[0]
    min_w = get_setting('min_withdraw')
    if res[0] < min_w:
        await call.answer(f"❌ Минимум ${min_w}", show_alert=True)
    else:
        await bot.send_message(LOG_CHANNEL_ID, f"💸 **ВЫВОД**\nЮзер: {res[1]}\nСумма: ${res[0]:.2f}")
        await call.answer("✅ Заявка отправлена!", show_alert=True)

@dp.callback_query(F.data == "back_to_main")
async def back(call: types.CallbackQuery):
    await smart_edit(call, "🚀 Главное меню", main_kb(call.from_user.id))

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
