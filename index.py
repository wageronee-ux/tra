import os
import telebot
from flask import Flask, request
from supabase import create_client, Client

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# Ваш ID обязательно строкой
ADMIN_ID = "8040642138" 

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- ГЛАВНОЕ МЕНЮ ---
def get_main_menu(user_id):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(telebot.types.KeyboardButton("👤 Мой профиль"))
    markup.add(telebot.types.KeyboardButton("🏆 ТОП лидеров"), telebot.types.KeyboardButton("🔗 Реф. ссылка"))
    markup.add(telebot.types.KeyboardButton("💸 Вывести средства"))
    
    if str(user_id) == ADMIN_ID:
        markup.add(telebot.types.KeyboardButton("⚙️ Админ-панель"))
    return markup

# --- ОБРАБОТЧИК /START ---
@bot.message_handler(commands=['start'])
def start_handler(message):
    uid = str(message.from_user.id) # Принудительно в строку
    try:
        # Проверка регистрации
        user_check = supabase.table("users").select("*").eq("user_id", uid).execute()
        
        if not user_check.data:
            referrer = None
            args = message.text.split()
            if len(args) > 1 and args[1] != uid:
                referrer = str(args[1])

            supabase.table("users").insert({
                "user_id": uid,
                "username": message.from_user.username or "NoUser",
                "first_name": message.from_user.first_name or "User",
                "balance": 0.0,
                "refs_count": 0,
                "referrer_id": referrer
            }).execute()

            if referrer:
                # Начисление за реферала
                r_data = supabase.table("users").select("balance", "refs_count").eq("user_id", referrer).execute()
                if r_data.data:
                    new_bal = float(r_data.data[0]['balance']) + 0.1
                    new_cnt = int(r_data.data[0]['refs_count']) + 1
                    supabase.table("users").update({"balance": new_bal, "refs_count": new_cnt}).eq("user_id", referrer).execute()

        bot.send_message(
            message.chat.id, 
            f"👋 Привет, {message.from_user.first_name}!\nВоспользуйся меню ниже:", 
            reply_markup=get_main_menu(uid)
        )
    except Exception as e:
        print(f"Start Error: {e}")

# --- ОБРАБОТКА КНОПОК МЕНЮ ---
@bot.message_handler(func=lambda m: True)
def menu_logic(message):
    uid = str(message.from_user.id)
    cid = message.chat.id

    try:
        if message.text == "👤 Мой профиль":
            # EQ фильтр теперь точно со строкой
            res = supabase.table("users").select("balance", "refs_count").eq("user_id", uid).execute()
            if res.data:
                data = res.data[0]
                msg = (
                    f"👤 **ВАШ ПРОФИЛЬ**\n"
                    f"────────────────────\n"
                    f"💰 Баланс: `{data['balance']}$` \n"
                    f"👥 Рефералы: `{data['refs_count']}` чел."
                )
                bot.send_message(cid, msg, parse_mode="Markdown")

        elif message.text == "🔗 Реф. ссылка":
            bot_username = bot.get_me().username
            bot.send_message(cid, f"🔗 Ссылка для друзей:\n`https://t.me/{bot_username}?start={uid}`", parse_mode="Markdown")

        elif message.text == "🏆 ТОП лидеров":
            top = supabase.table("users").select("first_name", "refs_count").order("refs_count", desc=True).limit(10).execute()
            text = "🏆 **ТОП 10 ПРИГЛАСИТЕЛЕЙ**\n\n"
            for i, u in enumerate(top.data, 1):
                text += f"{i}. {u['first_name']} — `{u['refs_count']}` чел.\n"
            bot.send_message(cid, text, parse_mode="Markdown")

        elif message.text == "💸 Вывести средства":
            bot.send_message(cid, "❌ Минимальный вывод: **10$**")

    except Exception as e:
        print(f"Menu Error: {e}")

# --- WEBHOOK SECTION ---
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Error", 403
