import os
import telebot
from flask import Flask, request
from supabase import create_client, Client

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_ID = "8040642138" 

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Состояния для админки (упрощенно)
user_state = {}

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

# --- ОБРАБОТЧИКИ СООБЩЕНИЙ ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    # Регистрация через RPC или Upsert для стабильности
    supabase.table("users").upsert({
        "user_id": uid, 
        "first_name": message.from_user.first_name,
        "username": message.from_user.username
    }).execute()
    
    bot.send_message(
        message.chat.id,
        f"🔥 **ДОБРО ПОЖАЛОВАТЬ, {message.from_user.first_name.upper()}!**\n\n"
        "Зарабатывай на приглашениях и прокачивай профиль!",
        parse_mode="Markdown",
        reply_markup=get_main_kb(uid)
    )

@bot.message_handler(func=lambda m: str(m.from_user.id) == ADMIN_ID)
def admin_inputs(message):
    uid = str(message.from_user.id)
    state = user_state.get(uid)

    if state == 'awaiting_broadcast':
        user_state[uid] = None
        users = supabase.table("users").select("user_id").execute()
        count = 0
        for u in users.data:
            try:
                bot.send_message(u['user_id'], message.text)
                count += 1
            except: pass
        bot.send_message(message.chat.id, f"✅ Рассылка завершена. Получили: {count} чел.")

    elif state == 'awaiting_balance_id':
        user_state[uid] = f"give_bal_{message.text}"
        bot.send_message(message.chat.id, "Введите сумму (например, 5.5):")

    elif state and state.startswith('give_bal_'):
        target_id = state.replace('give_bal_', '')
        try:
            amount = float(message.text)
            res = supabase.table("users").select("balance").eq("user_id", target_id).execute()
            if res.data:
                new_bal = float(res.data[0]['balance'] or 0) + amount
                supabase.table("users").update({"balance": new_bal}).eq("user_id", target_id).execute()
                bot.send_message(message.chat.id, f"✅ Баланс юзера {target_id} обновлен: {new_bal}$")
                bot.send_message(target_id, f"💰 Вам начислено {amount}$!")
            user_state[uid] = None
        except ValueError:
            bot.send_message(message.chat.id, "❌ Ошибка: введите число.")

# --- CALLBACKS ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = str(call.from_user.id)
    cid = call.message.chat.id

    try:
        if call.data == "profile":
            res = supabase.table("users").select("*").eq("user_id", uid).execute()
            if res.data:
                u = res.data[0]
                text = (f"📋 **ВАШ АККАУНТ**\n"
                        f"──────────────────\n"
                        f"💰 Баланс: `{u.get('balance', 0)}$`\n"
                        f"👥 Рефералы: `{u.get('refs_count', 0)}` чел.")
                bot.send_message(cid, text, parse_mode="Markdown", reply_markup=get_main_kb(uid))

        elif call.data == "admin_main":
            akb = telebot.types.InlineKeyboardMarkup()
            akb.add(telebot.types.InlineKeyboardButton("📢 Рассылка", callback_data="adm_bc"))
            akb.add(telebot.types.InlineKeyboardButton("💵 Выдать баланс", callback_data="adm_give"))
            bot.send_message(cid, "🛠 **АДМИН-МЕНЮ**", reply_markup=akb)

        elif call.data == "adm_bc":
            user_state[uid] = 'awaiting_broadcast'
            bot.send_message(cid, "📝 Введите текст для рассылки всем пользователям:")

        elif call.data == "adm_give":
            user_state[uid] = 'awaiting_balance_id'
            bot.send_message(cid, "🆔 Введите Telegram ID пользователя, которому начислить $:")

        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Error: {e}")

@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Error", 403
