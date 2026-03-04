import os
import telebot
from flask import Flask, request
from supabase import create_client, Client

# Конфигурация
TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# Подключаемся через HTTP API (порт 443)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    first_name = message.from_user.first_name or "User"
 @bot.message_handler(commands=['ref', 'referral'])
def referral_menu(message):
    user_id = message.from_user.id
    # Получаем username бота динамически
    bot_info = bot.get_me()
    bot_username = bot_info.username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    
    try:
        # Запрос к базе
        res = supabase.table("users").select("refs_count").eq("user_id", user_id).execute()
        
        if res.data:
            count = res.data[0].get("refs_count", 0)
            text = (
                f"👥 *Реферальное меню*\n\n"
                f"🔗 Твоя ссылка для приглашения:\n`{ref_link}`\n\n"
                f"📊 Приглашено друзей: *{count}*"
            )
            bot.send_message(message.chat.id, text, parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, "❌ Сначала введи /start")
    except Exception as e:
        print(f"Ошибка в реф-меню: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка базы данных.")   
    # Реферальный ID из ссылки вида t.me/bot?start=12345
    ref_id = None
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])
    if ref_id == user_id: ref_id = None

    try:
        # Проверяем наличие пользователя в таблице 'users'
        res = supabase.table("users").select("user_id").eq("user_id", user_id).execute()
        
        if not res.data:
            # Создаем запись
            supabase.table("users").insert({
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "referrer_id": ref_id
            }).execute()
            
            # Если есть реферер, прибавляем ему +1
            if ref_id:
                ref_res = supabase.table("users").select("refs_count").eq("user_id", ref_id).execute()
                if ref_res.data:
                    old_count = ref_res.data[0].get("refs_count") or 0
                    supabase.table("users").update({"refs_count": old_count + 1}).eq("user_id", ref_id).execute()
            
            bot.reply_to(message, f"✨ Привет, {first_name}! Ты успешно зарегистрирован.")
        else:
            bot.reply_to(message, "Ты уже в игре! Используй меню для навигации.")
            
    except Exception as e:
        print(f"Supabase Error: {e}")
        bot.reply_to(message, "⚠️ Ошибка базы данных. Попробуй позже.")

@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403

