import os
import telebot
from flask import Flask, request
from supabase import create_client, Client

# Конфигурация
TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_ID = 8040642138  

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def main_keyboard(user_id):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        telebot.types.InlineKeyboardButton("🏆 ТОП 10", callback_data="top_list"),
        telebot.types.InlineKeyboardButton("🔗 Ссылка", callback_data="ref_menu"),
        telebot.types.InlineKeyboardButton("💸 Вывод", callback_data="withdraw")
    )
    if user_id == ADMIN_ID:
        markup.add(telebot.types.InlineKeyboardButton("⚙️ Админ", callback_data="admin_panel"))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    # ВСЕГДА приводим к строке перед отправкой в Supabase
    uid = str(message.from_user.id)
    try:
        # Проверяем пользователя
        res = supabase.table("users").select("user_id").eq("user_id", uid).execute()
        
        if not res.data:
            # Реферальная логика
            ref_id = None
            args = message.text.split()
            if len(args) > 1 and args[1].isdigit() and args[1] != uid:
                ref_id = args[1]
            
            supabase.table("users").insert({
                "user_id": uid, 
                "username": message.from_user.username or "none",
                "first_name": message.from_user.first_name or "User",
                "referrer_id": ref_id,
                "balance": 0.0,
                "refs_count": 0
            }).execute()
            
            if ref_id:
                # Начисляем бонус пригласителю (обязательно через строку)
                r_res = supabase.table("users").select("balance", "refs_count").eq("user_id", str(ref_id)).execute()
                if r_res.data:
                    new_bal = float(r_res.data[0]['balance']) + 0.1
                    new_count = int(r_res.data[0]['refs_count']) + 1
                    supabase.table("users").update({"balance": new_bal, "refs_count": new_count}).eq("user_id", str(ref_id)).execute()

        bot.send_message(message.chat.id, "🚀 Бот готов к работе!", reply_markup=main_keyboard(message.from_user.id))
    except Exception as e:
        print(f"Error: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка базы данных.")

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    # 1. СРАЗУ отвечаем Telegram (исправляет 'query is too old')
    try:
        bot.answer_callback_query(call.id)
    except:
        pass

    uid = str(call.from_user.id)

    if call.data == "profile":
        # Используем .eq("user_id", str(uid)) для гарантии
        res = supabase.table("users").select("balance", "refs_count").eq("user_id", uid).execute()
        if res.data:
            data = res.data[0]
            bot.send_message(call.message.chat.id, f"👤 Профиль\n💰 Баланс: ${data['balance']}\n👥 Рефералы: {data['refs_count']}")

    elif call.data == "ref_menu":
        bot.send_message(call.message.chat.id, f"🔗 Ссылка:\n`https://t.me/{(bot.get_me()).username}?start={uid}`", parse_mode="Markdown")

    elif call.data == "top_list":
        res = supabase.table("users").select("first_name", "refs_count").order("refs_count", desc=True).limit(10).execute()
        text = "🏆 ТОП 10:\n"
        for i, u in enumerate(res.data, 1):
            text += f"{i}. {u['first_name']} — {u['refs_count']} чел.\n"
        bot.send_message(call.message.chat.id, text)

@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403
