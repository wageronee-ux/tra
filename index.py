import os
import telebot
from flask import Flask, request
from supabase import create_client, Client

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_ID = "8040642138"  # Всегда используем строку для ID

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- ГЛАВНОЕ МЕНЮ (REPLY КЛАВИАТУРА) ---
def get_main_menu(user_id):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    # Кнопки будут располагаться внизу вместо инлайна
    markup.add(telebot.types.KeyboardButton("👤 Мой профиль"))
    markup.add(telebot.types.KeyboardButton("🏆 ТОП лидеров"), telebot.types.KeyboardButton("🔗 Реф. ссылка"))
    markup.add(telebot.types.KeyboardButton("💸 Вывести средства"))
    
    if str(user_id) == ADMIN_ID:
        markup.add(telebot.types.KeyboardButton("⚙️ Админ-панель"))
    return markup

# --- ОБРАБОТЧИК /START ---
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id_str = str(message.from_user.id) # ГЛАВНОЕ ИСПРАВЛЕНИЕ: ID в строку
    try:
        # Проверяем пользователя
        user_res = supabase.table("users").select("*").eq("user_id", user_id_str).execute()
        
        if not user_res.data:
            # Регистрация нового пользователя
            referrer = None
            args = message.text.split()
            if len(args) > 1 and args[1] != user_id_str:
                referrer = args[1]

            supabase.table("users").insert({
                "user_id": user_id_str,
                "username": message.from_user.username or "NoUser",
                "first_name": message.from_user.first_name or "User",
                "balance": 0.0,
                "refs_count": 0,
                "referrer_id": referrer
            }).execute()

            # Если есть реферер - начисляем бонус (0.1$)
            if referrer:
                ref_id = str(referrer)
                r_data = supabase.table("users").select("balance", "refs_count").eq("user_id", ref_id).execute()
                if r_data.data:
                    new_bal = float(r_data.data[0]['balance']) + 0.1
                    new_cnt = int(r_data.data[0]['refs_count']) + 1
                    supabase.table("users").update({"balance": new_bal, "refs_count": new_cnt}).eq("user_id", ref_id).execute()

        welcome_text = (
            f"👋 **Привет, {message.from_user.first_name}!**\n"
            f"────────────────────\n"
            f"Используйте меню ниже для работы с ботом."
        )
        bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_menu(user_id_str), parse_mode="Markdown")
        
    except Exception as e:
        print(f"Error in start: {e}")

# --- ОБРАБОТКА НАЖАТИЙ КНОПОК МЕНЮ ---
@bot.message_handler(func=lambda message: True)
def handle_menu_buttons(message):
    uid = str(message.from_user.id)
    cid = message.chat.id

    try:
        if message.text == "👤 Мой профиль":
            res = supabase.table("users").select("balance", "refs_count").eq("user_id", uid).execute()
            if res.data:
                d = res.data[0]
                text = (
                    f"👤 **ВАШ ПРОФИЛЬ**\n"
                    f"────────────────────\n"
                    f"💰 **Баланс:** `{d['balance']}$` \n"
                    f"👥 **Рефералы:** `{d['refs_count']}` чел.\n"
                    f"────────────────────\n"
                    f"💳 Статус: **Активен**"
                )
                bot.send_message(cid, text, parse_mode="Markdown")

        elif message.text == "🔗 Реф. ссылка":
            bot_info = bot.get_me()
            link = f"https://t.me/{bot_info.username}?start={uid}"
            bot.send_message(cid, f"🔗 **Ваша ссылка:**\n\n`{link}`", parse_mode="Markdown")

        elif message.text == "🏆 ТОП лидеров":
            res = supabase.table("users").select("first_name", "refs_count").order("refs_count", desc=True).limit(10).execute()
            top_msg = "🏆 **ТОП 10 ЛИДЕРОВ**\n────────────────────\n"
            for i, user in enumerate(res.data, 1):
                top_msg += f"{i}. {user['first_name']} — `{user['refs_count']}` реф.\n"
            bot.send_message(cid, top_msg, parse_mode="Markdown")

        elif message.text == "💸 Вывести средства":
            bot.send_message(cid, "❌ **Ошибка**\nМинимальная сумма вывода: `10$`")

    except Exception as e:
        print(f"Error in menu: {e}")

# --- WEBHOOK ---
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403
