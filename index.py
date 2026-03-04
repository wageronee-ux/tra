import asyncio
import os
from flask import Flask, request
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Update, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandObject, Command

app = Flask(__name__)
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 123456789  # !!! ЗАМЕНИ НА СВОЙ ID (узнай в @userinfobot)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Имитация базы данных (в реальности лучше использовать PostgreSQL/TinyDB)
users_db = {} # {user_id: {'referrer': ref_id, 'referrals_count': 0}}

# --- КНОПКИ ---
def get_main_menu(user_id):
    buttons = [
        [InlineKeyboardButton(text="🔗 Моя ссылка", callback_data="my_ref")],
        [InlineKeyboardButton(text="🎁 Бонусы", callback_data="bonuses")]
    ]
    if user_id == ADMIN_ID:
        buttons.append([InlineKeyboardButton(text="📊 Админ-панель", callback_data="admin_stats")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def start_handler(message: types.Message, command: CommandObject):
    user_id = message.from_user.id
    args = command.args # Получаем ID пригласителя из ссылки
    
    if user_id not in users_db:
        referrer = int(args) if args and args.isdigit() else None
        users_db[user_id] = {'referrer': referrer, 'referrals_count': 0}
        if referrer and referrer in users_db:
            users_db[referrer]['referrals_count'] += 1

    # Ссылка на любую GIF в интернете
    welcome_gif = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJueGZ3bmZ3bmZ3bmZ3/3o7abKhOpu0NPGVYSE/giphy.gif"
    
    await message.answer_animation(
        animation=welcome_gif,
        caption=f"👋 Привет, {message.from_user.first_name}!\nДобро пожаловать в реф-систему.",
        reply_markup=get_main_menu(user_id)
    )

@dp.callback_query()
async def callback_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if callback.data == "my_ref":
        bot_info = await bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        count = users_db.get(user_id, {}).get('referrals_count', 0)
        await callback.message.edit_caption(
            caption=f"📢 Твоя ссылка: `{ref_link}`\n👥 Приглашено: {count}",
            parse_mode="Markdown",
            reply_markup=get_main_menu(user_id)
        )
    
    elif callback.data == "admin_stats":
        total_users = len(users_db)
        await callback.answer(f"Всего пользователей: {total_users}", show_alert=True)

# --- ЛОГИКА VERCEL ---
async def main_process(update_dict):
    update = Update.model_validate(update_dict, context={"bot": bot})
    try:
        await dp.feed_update(bot, update)
    finally:
        await bot.session.close()

@app.route('/', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        update_dict = request.get_json()
        if update_dict:
            asyncio.run(main_process(update_dict))
        return "OK", 200
    return "Система активна!", 200
