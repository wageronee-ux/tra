import os
import telebot
from flask import Flask, request
from supabase import create_client, Client

# --- 1. КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_ID = 8040642138  
CHANNEL_ID = "@traffchanel" 
LOG_CHANNEL_ID = -1003850107854 

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. КЛАВИАТУРЫ ---
def main_keyboard(user_id):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        telebot.types.InlineKeyboardButton("🏆 ТОП 10", callback_data="top_list"),
        telebot.types.InlineKeyboardButton("🔗 Ссылка", callback_data="ref_menu"),
        telebot.types.InlineKeyboardButton("💸 Вывод", callback_data="withdraw_money")
    )
    if user_id == ADMIN_ID:
        markup.add(telebot.types.InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_main"))
    return markup

def sub_keyboard():
    markup = telebot.types.InlineKeyboardMarkup()
    url_button = telebot.types.InlineKeyboardButton(text="Подписаться", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")
    check_button = telebot.types.InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")
    markup.add(url_button)
    markup.add(check_button)
    return markup

def check_sub(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_ID, user_id).status
        return status in ['member', 'administrator', 'creator']
    except: return False

# --- 3. ОБРАБОТКА START ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    if not check_sub(message.from_user.id):
        bot.send_message(message.chat.id, f"⚠️ Подпишитесь на канал для работы!", reply_markup=sub_keyboard())
        return

    # Логика рефералов
    ref_id = None
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        ref_id = args[1]
    if ref_id == uid: ref_id = None

    try:
        res = supabase.table("users").select("*").eq("user_id", uid).execute()
        if not res.data:
            supabase.table("users").insert({
                "user_id": uid, "username": message.from_user.username or "none",
                "first_name": message.from_user.first_name or "User",
                "referrer_id": ref_id, "balance": 0, "refs_count": 0
            }).execute()
            if ref_id:
                r_res = supabase.table("users").select("balance", "refs_count").eq("user_id", ref_id).execute()
                if r_res.data:
                    supabase.table("users").update({
                        "balance": float(r_res.data[0]['balance']) + 0.1,
                        "refs_count": int(r_res.data[0]['refs_count']) + 1
                    }).eq("user_id", ref_id).execute()
        bot.send_message(message.chat.id, "🚀 Добро пожаловать!", reply_markup=main_keyboard(message.from_user.id))
    except:
        bot.send_message(message.chat.id, "⚠️ Ошибка базы. Попробуйте позже.")

# --- 4. ОБРАБОТКА КНОПОК (БЕЗ РЕДАКТИРОВАНИЯ ДЛЯ СКОРОСТИ) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    uid = str(call.from_user.id)
    
    # Сначала отвечаем Telegram, чтобы убрать "часики"
    try: bot.answer_callback_query(call.id)
    except: pass

    if call.data == "check_sub":
        if check_sub(call.from_user.id):
            bot.send_message(call.message.chat.id, "✅ Спасибо за подписку!", reply_markup=main_keyboard(call.from_user.id))
        else:
            bot.send_message(call.message.chat.id, "❌ Вы всё еще не подписаны.")

    elif call.data == "profile":
        res = supabase.table("users").select("balance", "refs_count").eq("user_id", uid).execute()
        if res.data:
            msg = f"👤 **Профиль**\n\n💰 Баланс: `${res.data[0]['balance']}`\n👥 Рефералов: `{res.data[0]['refs_count']}`"
            bot.send_message(call.message.chat.id, msg, parse_mode="Markdown")

    elif call.data == "ref_menu":
        link = f"https://t.me/{(bot.get_me()).username}?start={uid}"
        bot.send_message(call.message.chat.id, f"🔗 **Ваша ссылка:**\n`{link}`", parse_mode="Markdown")

    elif call.data == "top_list":
        res = supabase.table("users").select("first_name", "refs_count").order("refs_count", desc=True).limit(10).execute()
        text = "🏆 **ТОП 10**\n\n"
        for i, u in enumerate(res.data, 1):
            text += f"{i}. {u['first_name']} — {u['refs_count']} чел.\n"
        bot.send_message(call.message.chat.id, text)

    elif call.data == "withdraw_money":
        res = supabase.table("users").select("balance").eq("user_id", uid).execute()
        bal = res.data[0]['balance'] if res.data else 0
        if float(bal) < 5.0:
            bot.send_message(call.message.chat.id, f"❌ Минимум $5.00. У вас ${bal}")
        else:
            bot.send_message(LOG_CHANNEL_ID, f"💸 ЗАЯВКА: `{uid}` — ${bal}")
            bot.send_message(call.message.chat.id, "✅ Заявка принята!")

# --- 5. ВЕБХУК ---
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403
