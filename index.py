import os
import telebot
from flask import Flask, request
from supabase import create_client, Client

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_ID = "8040642138" # ID в кавычках (строка)

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- ГЛАВНОЕ МЕНЮ (Reply-кнопки надежнее для Vercel) ---
def get_main_menu():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(telebot.types.KeyboardButton("👤 Профиль"))
    markup.add(telebot.types.KeyboardButton("🏆 ТОП лидеров"), telebot.types.KeyboardButton("🔗 Реф. ссылка"))
    markup.add(telebot.types.KeyboardButton("💸 Вывод"))
    return markup

@bot.message_handler(commands=['start'])
def start_cmd(message):
    uid = str(message.from_user.id)
    try:
        # Проверяем пользователя
        check = supabase.table("users").select("user_id").eq("user_id", uid).execute()
        
        if not check.data:
            # Регистрация нового
            supabase.table("users").insert({
                "user_id": uid,
                "first_name": message.from_user.first_name or "User",
                "balance": 0.0,
                "refs_count": 0
            }).execute()
        
        bot.send_message(message.chat.id, f"Привет, {message.from_user.first_name}!", reply_markup=get_main_menu())
    except Exception as e:
        print(f"Error in start: {e}")

@bot.message_handler(func=lambda m: True)
def handle_menu(message):
    uid = str(message.from_user.id)
    
    try:
        if message.text == "👤 Профиль":
            # Используем .select("*") так как в логах он работает стабильнее
            res = supabase.table("users").select("*").eq("user_id", uid).execute()
            if res.data:
                u = res.data[0]
                text = (
                    f"👤 **ВАШ ПРОФИЛЬ**\n"
                    f"──────────────────\n"
                    f"💰 Баланс: `{u.get('balance', 0)}$` \n"
                    f"👥 Рефералы: `{u.get('refs_count', 0)}`"
                )
                bot.send_message(message.chat.id, text, parse_mode="Markdown")

        elif message.text == "🏆 ТОП лидеров":
            top = supabase.table("users").select("first_name, refs_count").order("refs_count", desc=True).limit(10).execute()
            text = "🏆 **ТОП 10**\n\n"
            for i, u in enumerate(top.data, 1):
                text += f"{i}. {u['first_name']} — `{u['refs_count']}` чел.\n"
            bot.send_message(message.chat.id, text, parse_mode="Markdown")

        elif message.text == "🔗 Реф. ссылка":
            bot_name = bot.get_me().username
            bot.send_message(message.chat.id, f"🔗 Ссылка для друзей:\n`https://t.me/{bot_name}?start={uid}`", parse_mode="Markdown")

    except Exception as e:
        print(f"Menu error: {e}")

# --- WEBHOOK ---
@app.route('/', methods=['POST'])
def process_webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403
