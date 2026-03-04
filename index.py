import asyncio
import os
from flask import Flask, request
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Update, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandObject, Command
from supabase import create_client, Client

app = Flask(__name__)

# Данные из Environment Variables
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

bot = Bot(token=TOKEN)
dp = Dispatcher()
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Временное хранилище для состояния админа (кто сейчас пишет рассылку)
admin_state = {}

# --- КНОПКИ ---
def get_main_menu(user_id):
    kb = [
        [InlineKeyboardButton(text="🔗 Моя ссылка", callback_data="my_ref")],
        [InlineKeyboardButton(text="🏆 ТОП по никам", callback_data="top_players")]
    ]
    if user_id == ADMIN_ID:
        kb.append([InlineKeyboardButton(text="⚙️ Админка", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Сделать рассылку", callback_data="start_broadcast")],
        [InlineKeyboardButton(text="📊 Статистика БД", callback_data="admin_stats")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def start_handler(message: types.Message, command: CommandObject):
    user_id = message.from_user.id
    username = message.from_user.username or "Скрыт"
    first_name = message.from_user.first_name
    
    # Регистрация в Supabase
    res = supabase.table("users").select("*").eq("user_id", user_id).execute()
    if not res.data:
        ref_id = int(command.args) if command.args and command.args.isdigit() else None
        supabase.table("users").insert({
            "user_id": user_id, "username": username, "first_name": first_name, "referrer_id": ref_id
        }).execute()
        if ref_id:
            supabase.rpc("increment_referrals", {"row_id": ref_id}).execute()

    await message.answer("👋 Добро пожаловать!", reply_markup=get_main_menu(user_id))

# ФУНКЦИЯ РАССЫЛКИ (только для админа)
@dp.callback_query(F.data == "start_broadcast")
async def start_broadcast(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    admin_state[ADMIN_ID] = "waiting_broadcast_text"
    await callback.message.answer("📝 Напиши текст или отправь фото для рассылки всем пользователям:")
    await callback.answer()

@dp.message()
async def handle_broadcast_message(message: types.Message):
    user_id = message.from_user.id
    
    # Если админ в режиме создания рассылки
    if user_id == ADMIN_ID and admin_state.get(ADMIN_ID) == "waiting_broadcast_text":
        admin_state[ADMIN_ID] = None # Выключаем режим
        
        # Получаем всех юзеров из БД
        users = supabase.table("users").select("user_id").execute()
        count = 0
        
        await message.answer(f"🚀 Начинаю рассылку на {len(users.data)} чел...")
        
        for u in users.data:
            try:
                # Копируем сообщение админа (текст, фото, видео — всё сработает)
                await message.copy_to(u['user_id'])
                count += 1
                await asyncio.sleep(0.05) # Защита от спам-фильтра Telegram
            except Exception:
                continue # Если заблокировали — идем дальше
        
        await message.answer(f"✅ Рассылка завершена! Получили: {count} чел.")
    else:
        # Обычный ответ, если это не рассылка
        await message.answer("Используй кнопки меню 👇", reply_markup=get_main_menu(user_id))

@dp.callback_query()
async def callback_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if callback.data == "admin_menu":
        await callback.message.edit_text("🛠 Панель управления:", reply_markup=get_admin_menu())
    
    elif callback.data == "admin_stats":
        res = supabase.table("users").select("user_id", count="exact").execute()
        await callback.answer(f"Юзеров: {res.count}", show_alert=True)
        
    elif callback.data == "top_players":
        res = supabase.table("users").select("username, referrals_count").order("referrals_count", desc=True).limit(10).execute()
        text = "🏆 **ТОП 10:**\n" + "\n".join([f"{i+1}. @{u['username']} — {u['referrals_count']}" for i, u in enumerate(res.data)])
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_main_menu(user_id))

    elif callback.data == "back_to_main":
        await callback.message.edit_text("Главное меню:", reply_markup=get_main_menu(user_id))

# --- ЛОГИКА VERCEL ---
async def main_process(update_dict):
    update = Update.model_validate(update_dict, context={"bot": bot})
    try: await dp.feed_update(bot, update)
    finally: await bot.session.close()

@app.route('/', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        asyncio.run(main_process(request.get_json()))
    return "OK", 200
