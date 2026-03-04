import os
import telebot
from flask import Flask, request
from supabase import create_client, Client

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_ID = 8040642138  

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- КЛАВИАТУРА (REPLY МЕНЮ) ---
def main_menu_keyboard(user_id):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(telebot.types.KeyboardButton("👤 Мой профиль"))
    markup.add(telebot.types.KeyboardButton("🏆 ТОП лидеров"), telebot.types.KeyboardButton("🔗 Реф. ссылка"))
    markup.add(telebot.types.KeyboardButton("💸 Вывести $"))
    if user_id == ADMIN_ID:
        markup.add(telebot.types.KeyboardButton("⚙️ Админ-панель"))
    return markup

# --- ОБРАБОТЧИК /START ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id) # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: всегда строка
    try:
        res = supabase.table("users").select("user_id").eq("user_id", uid).execute()
        
        if not res.data:
            ref_id = None
            args = message.text.split()
            if len(args) > 1 and args[1] != uid:
                ref_id = args[1]
            
            supabase.table("users").insert({
                "user_id": uid,
                "username": message.from_user.username or "none",
                "first_name": message.from_user.first_name or "User",
                "balance": 0.0,
                "refs_count": 0,
                "referrer_id": ref_id
            }).execute()
            
            if ref_id:
                # Начисляем бонус пригласителю
                r_res = supabase.table("users").select("balance", "refs_count").eq("user_id", str(ref_id)).execute()
                if r_res.data:
                    new_bal = float(r_res.data[0]['balance']) + 0.1
                    new_count = int(r_res.data[0]['refs_count']) + 1
                    supabase.table("users").update({"balance": new_bal, "refs_count": new_count}).eq("user_id", str(ref_id)).execute()

        welcome = f"👋 Привет, {message.from_user.first_name}!\n────────────────────\nИспользуй меню ниже для навигации 👇"
        bot.send_message(message.chat.id, welcome, reply_markup=main_menu_keyboard(message.from_user.id), parse_mode="Markdown")
    except Exception as e:
        print(f"Error in start: {e}")

# --- ОБРАБОТКА ТЕКСТОВЫХ КНОПОК ---
@bot.message_handler(func=lambda m: True)
def handle_menu(message):
    uid = str(message.from_user.id)
    cid = message.chat.id

    try:
        if message.text == "👤 Мой профиль":
            res = supabase.table("users").select("balance, refs_count").eq("user_id", uid).execute()
            if res.data:
                d = res.data[0]
                text = (f"👤 **ВАШ ПРОФИЛЬ**\n────────────────────\n"
                        f"💰 **Баланс:** `{d['balance']}$` \n"
                        f"👥 **Рефералы:** `{d['refs_count']}` чел.")
                bot.send_message(cid, text, parse_mode="Markdown")

        elif message.text == "🔗 Реф. ссылка":
            b_info = bot.get_me()
            link = f"https://t.me/{b_info.username}?start={uid}"
            bot.send_message(cid, f"🔗 **Ваша ссылка:**\n`{link}`", parse_mode="Markdown")

        elif message.text == "🏆 ТОП лидеров":
            res = supabase.table("users").select("first_name, refs_count").order("refs_count", desc=True).limit(10).execute()
            top = "🏆 **ТОП 10 ЛИДЕРОВ**\n────────────────────\n"
            for i, u in enumerate(res.data, 1):
                top += f"{i}. {u['first_name']} — `{u['refs_count']}` чел.\n"
            bot.send_message(cid, top, parse_mode="Markdown")

        elif message.text == "💸 Вывести $":
            bot.send_message(cid, "❌ **Ошибка**\nМинимальный вывод: `10$`\nВаш баланс слишком мал.", parse_mode="Markdown")

    except Exception as e:
        print(f"Error: {e}")

# --- FLASK WEBHOOK ---
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403
