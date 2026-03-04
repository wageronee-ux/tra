import os
import telebot
from flask import Flask, request
from supabase import create_client, Client

# Настройки
TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_ID = 8040642138  

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- ГЛАВНОЕ МЕНЮ (REPLY КЛАВИАТУРА) ---
def get_main_menu(user_id):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(telebot.types.KeyboardButton("👤 Мой профиль"))
    markup.add(telebot.types.KeyboardButton("🏆 ТОП лидеров"), telebot.types.KeyboardButton("🔗 Реф. ссылка"))
    markup.add(telebot.types.KeyboardButton("💸 Вывести средства"))
    
    if user_id == ADMIN_ID:
        markup.add(telebot.types.KeyboardButton("⚙️ Админ-панель"))
    return markup

# --- ОБРАБОТЧИК /START ---
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id_str = str(message.from_user.id) # ПРЕВРАЩАЕМ В СТРОКУ ДЛЯ SUPABASE
    try:
        # Проверяем наличие пользователя
        user_data = supabase.table("users").select("*").eq("user_id", user_id_str).execute()
        
        if not user_data.data:
            # Логика регистрации
            referrer = None
            args = message.text.split()
            if len(args) > 1 and args[1] != user_id_str:
                referrer = args[1]

            supabase.table("users").insert({
                "user_id": user_id_str,
                "username": message.from_user.username or "NoUser",
                "first_name": message.from_user.first_name,
                "balance": 0.0,
                "refs_count": 0,
                "referrer_id": referrer
            }).execute()

            # Если есть реферер - начисляем бонус
            if referrer:
                ref_res = supabase.table("users").select("balance", "refs_count").eq("user_id", str(referrer)).execute()
                if ref_res.data:
                    new_bal = float(ref_res.data[0]['balance']) + 0.1
                    new_cnt = int(ref_res.data[0]['refs_count']) + 1
                    supabase.table("users").update({"balance": new_bal, "refs_count": new_cnt}).eq("user_id", str(referrer)).execute()

        welcome_msg = (
            f"👋 **Привет, {message.from_user.first_name}!**\n"
            f"────────────────────\n"
            f"Добро пожаловать в нашу партнерскую сеть.\n"
            f"Используйте меню ниже для навигации."
        )
        bot.send_message(message.chat.id, welcome_msg, reply_markup=get_main_menu(message.from_user.id), parse_mode="Markdown")
    except Exception as e:
        print(f"Start Error: {e}")

# --- ОБРАБОТКА НАЖАТИЙ КНОПОК МЕНЮ ---
@bot.message_handler(func=lambda message: True)
def handle_text_buttons(message):
    uid = str(message.from_user.id)
    cid = message.chat.id

    try:
        if message.text == "👤 Мой профиль":
            res = supabase.table("users").select("balance", "refs_count").eq("user_id", uid).execute()
            if res.data:
                data = res.data[0]
                text = (
                    f"👤 **ВАШ ПРОФИЛЬ**\n"
                    f"────────────────────\n"
                    f"💰 **Баланс:** `{data['balance']}$` \n"
                    f"👥 **Рефералы:** `{data['refs_count']}` чел.\n"
                    f"────────────────────\n"
                    f"💳 Статус: **Активен**"
                )
                bot.send_message(cid, text, parse_mode="Markdown")

        elif message.text == "🔗 Реф. ссылка":
            bot_name = bot.get_me().username
            link = f"https://t.me/{bot_name}?start={uid}"
            text = f"🔗 **Ваша ссылка для приглашений:**\n\n`{link}`"
            bot.send_message(cid, text, parse_mode="Markdown")

        elif message.text == "🏆 ТОП лидеров":
            res = supabase.table("users").select("first_name", "refs_count").order("refs_count", desc=True).limit(10).execute()
            top_text = "🏆 **ТОП 10 ПРИГЛАСИТЕЛЕЙ**\n"
            top_text += "────────────────────\n"
            for i, u in enumerate(res.data, 1):
                top_text += f"{i}. {u['first_name']} — `{u['refs_count']}` чел.\n"
            bot.send_message(cid, top_text, parse_mode="Markdown")

        elif message.text == "💸 Вывести средства":
            bot.send_message(cid, "❌ **Ошибка**\nМинимальная сумма для вывода: `10$`")

    except Exception as e:
        print(f"Menu Error: {e}")

# --- WEBHOOK SETUP ---
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403
