import os
import telebot
from flask import Flask, request
from supabase import create_client, Client

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_ID = "8040642138" 

# Ссылки на медиа (замените на свои, если хотите другие)
GIF_WELCOME = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExOHpueGZ3bmZ3bmZ3bmZ3bmZ3bmZ3bmZ3bmZ3JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/3o7TKSjRrfIPJeiT4s/giphy.gif"
PHOTO_PROFILE = "https://i.imgur.com/8n9Xp8R.png" 

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- КЛАВИАТУРЫ ---
def get_main_kb(uid):
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        telebot.types.InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        telebot.types.InlineKeyboardButton("🏆 Топ Лидеров", callback_data="top")
    )
    kb.add(
        telebot.types.InlineKeyboardButton("🔗 Реф. ссылка", callback_data="ref"),
        telebot.types.InlineKeyboardButton("💸 Вывод", callback_data="withdraw")
    )
    if str(uid) == ADMIN_ID:
        kb.add(telebot.types.InlineKeyboardButton("⚙️ АДМИН ПАНЕЛЬ", callback_data="admin_main"))
    return kb

# --- ОБРАБОТКА КОМАНД ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    # Регистрация (упрощенная для логов)
    supabase.table("users").upsert({
        "user_id": uid, 
        "first_name": message.from_user.first_name,
        "username": message.from_user.username
    }).execute()
    
    bot.send_animation(
        message.chat.id, GIF_WELCOME,
        caption=f"🔥 **ДОБРО ПОЖАЛОВАТЬ, {message.from_user.first_name.upper()}!**\n\n"
                f"Зарабатывай на приглашениях друзей.\n"
                f"Жми кнопки ниже, чтобы начать 👇",
        parse_mode="Markdown",
        reply_markup=get_main_kb(uid)
    )

# --- CALLBACK HANDLER (МЯСО ТУТ) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = str(call.from_user.id)
    cid = call.message.chat.id
    mid = call.message.message_id

    try:
        if call.data == "profile":
            res = supabase.table("users").select("*").eq("user_id", uid).execute()
            u = res.data[0]
            text = (f"📋 **ВАШ АККАУНТ**\n"
                    f"──────────────────\n"
                    f"👤 Имя: `{u['first_name']}`\n"
                    f"💰 Баланс: `{u.get('balance', 0)}$`\n"
                    f"👥 Рефералы: `{u.get('refs_count', 0)}` чел.")
            bot.edit_message_caption(text, cid, mid, parse_mode="Markdown", reply_markup=get_main_kb(uid))

        elif call.data == "ref":
            bot_username = bot.get_me().username
            link = f"https://t.me/{bot_username}?start={uid}"
            bot.send_message(cid, f"🚀 **Твоя ссылка для приглашений:**\n\n`{link}`", parse_mode="Markdown")

        elif call.data == "withdraw":
            bot.answer_callback_query(call.id, "❌ Недостаточно средств для вывода (мин. 10$)", show_alert=True)

        elif call.data == "top":
            res = supabase.table("users").select("first_name, refs_count").order("refs_count", desc=True).limit(10).execute()
            top_msg = "🏆 **ТОП 10 ЛИДЕРОВ**\n\n"
            for i, user in enumerate(res.data, 1):
                top_msg += f"{i}. {user['first_name']} — `{user['refs_count']}` реф.\n"
            bot.send_message(cid, top_msg, parse_mode="Markdown")

        # --- АДМИНКА ---
        elif call.data == "admin_main":
            if uid != ADMIN_ID: return
            akb = telebot.types.InlineKeyboardMarkup()
            akb.add(telebot.types.InlineKeyboardButton("📊 Статистика базы", callback_data="adm_stats"))
            akb.add(telebot.types.InlineKeyboardButton("📢 Сделать рассылку", callback_data="adm_broadcast"))
            akb.add(telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))
            bot.edit_message_caption("🛠 **ПАНЕЛЬ УПРАВЛЕНИЯ**", cid, mid, reply_markup=akb)

        elif call.data == "adm_stats":
            count = supabase.table("users").select("user_id", count="exact").execute()
            bot.answer_callback_query(call.id, f"👥 Всего юзеров: {count.count}", show_alert=True)

        elif call.data == "back_to_main":
            bot.edit_message_caption("Выберите раздел:", cid, mid, reply_markup=get_main_kb(uid))

        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Callback Error: {e}")

# --- WEBHOOK ---
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Error", 403
