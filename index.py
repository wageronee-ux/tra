import os
import telebot
from flask import Flask, request
from supabase import create_client, Client

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_ID = "8040642138" 
CHANNEL_ID = "@vash_kanal" # Обязательно замените!
CHANNEL_LINK = "https://t.me/vash_kanal"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Хранилище временных состояний
user_state = {}

# --- ПРОВЕРКА ПОДПИСКИ ---
def is_subscribed(uid):
    try:
        status = bot.get_chat_member(CHANNEL_ID, uid).status
        return status in ['member', 'administrator', 'creator']
    except:
        return False

# --- КЛАВИАТУРЫ ---
def get_main_kb(uid):
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        telebot.types.InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        telebot.types.InlineKeyboardButton("🏆 Лидеры", callback_data="top")
    )
    kb.add(
        telebot.types.InlineKeyboardButton("🔗 Реф. ссылка", callback_data="ref"),
        telebot.types.InlineKeyboardButton("💸 Вывод", callback_data="withdraw")
    )
    if str(uid) == ADMIN_ID:
        kb.add(telebot.types.InlineKeyboardButton("⚙️ АДМИНКА", callback_data="admin_main"))
    return kb

# --- ОБРАБОТЧИКИ СООБЩЕНИЙ ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    
    if not is_subscribed(uid):
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("📢 Подписаться", url=CHANNEL_LINK))
        kb.add(telebot.types.InlineKeyboardButton("✅ Проверить", callback_data="check_sub"))
        bot.send_message(message.chat.id, "⚠️ **Доступ закрыт!**\nПодпишитесь на канал, чтобы продолжить.", 
                         reply_markup=kb, parse_mode="Markdown")
        return

    # Регистрация и реферал
    res = supabase.table("users").select("*").eq("user_id", uid).execute()
    if not res.data:
        ref_id = message.text.split()[1] if len(message.text.split()) > 1 else None
        supabase.table("users").insert({
            "user_id": uid, "first_name": message.from_user.first_name,
            "referrer_id": ref_id, "balance": 0.0, "refs_count": 0
        }).execute()
        
        if ref_id and ref_id != uid:
            r_data = supabase.table("users").select("balance, refs_count").eq("user_id", ref_id).execute()
            if r_data.data:
                new_bal = float(r_data.data[0]['balance'] or 0) + 0.5
                new_cnt = int(r_data.data[0]['refs_count'] or 0) + 1
                supabase.table("users").update({"balance": new_bal, "refs_count": new_cnt}).eq("user_id", ref_id).execute()
                try: bot.send_message(ref_id, "💎 +0.5$! Друг подписался по вашей ссылке.")
                except: pass

    bot.send_message(message.chat.id, f"👋 Привет, {message.from_user.first_name}!", reply_markup=get_main_kb(uid))

# Обработка ввода для вывода/админки
@bot.message_handler(func=lambda m: True)
def handle_text(message):
    uid = str(message.from_user.id)
    state = user_state.get(uid)

    if state == 'awaiting_withdraw_wallet':
        wallet = message.text
        user_state[uid] = None
        # Отправляем заявку админу
        admin_text = f"🚨 **НОВАЯ ЗАЯВКА НА ВЫВОД**\n\nЮзер: `{uid}`\nКошелек: `{wallet}`"
        bot.send_message(ADMIN_ID, admin_text, parse_mode="Markdown")
        bot.send_message(message.chat.id, "✅ **Заявка отправлена!**\nАдминистратор проверит её в течение 24 часов.")

# --- CALLBACKS ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid, cid = str(call.from_user.id), call.message.chat.id

    if call.data == "check_sub":
        if is_subscribed(uid):
            bot.delete_message(cid, call.message.message_id)
            start(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ Вы не подписаны!", show_alert=True)

    elif call.data == "profile":
        u = supabase.table("users").select("*").eq("user_id", uid).execute().data[0]
        bot.send_message(cid, f"📋 **ВАШ ПРОФИЛЬ**\n\n💰 Баланс: `{u['balance']}$`", parse_mode="Markdown")

    elif call.data == "withdraw":
        u = supabase.table("users").select("balance").eq("user_id", uid).execute().data[0]
        if float(u['balance']) < 5.0: # Минималка 5$
            bot.answer_callback_query(call.id, "❌ Минимум для вывода: 5$", show_alert=True)
        else:
            user_state[uid] = 'awaiting_withdraw_wallet'
            bot.send_message(cid, "💳 **Введите номер вашего кошелька (TRC20/Card):**")

    elif call.data == "ref":
        bot_user = bot.get_me().username
        bot.send_message(cid, f"🔗 Ссылка: `https://t.me/{bot_user}?start={uid}`", parse_mode="Markdown")

    bot.answer_callback_query(call.id)

# --- WEBHOOK ---
@app.route('/', methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200
