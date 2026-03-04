import os
import telebot
from flask import Flask, request
from supabase import create_client, Client

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_ID = "8040642138" 
CHANNEL_ID = "@vash_kanal"  # Юзернейм канала с @
CHANNEL_LINK = "https://t.me/vash_kanal"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

user_state = {}

# --- ПРОВЕРКА ПОДПИСКИ ---
def check_sub(uid):
    try:
        status = bot.get_chat_member(CHANNEL_ID, uid).status
        return status in ['member', 'administrator', 'creator']
    except:
        return False

# --- КЛАВИАТУРЫ ---
def sub_kb():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_LINK))
    kb.add(telebot.types.InlineKeyboardButton("✅ Проверить подписку", callback_data="check_subscription"))
    return kb

def main_kb(uid):
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        telebot.types.InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        telebot.types.InlineKeyboardButton("🏆 Топ лидеров", callback_data="top")
    )
    kb.add(
        telebot.types.InlineKeyboardButton("🔗 Реф. ссылка", callback_data="ref"),
        telebot.types.InlineKeyboardButton("💸 Вывод", callback_data="withdraw")
    )
    if str(uid) == ADMIN_ID:
        kb.add(telebot.types.InlineKeyboardButton("🛠 АДМИН ПАНЕЛЬ", callback_data="admin_main"))
    return kb

# --- ОБРАБОТЧИК /START ---
@bot.message_handler(commands=['start'])
def start_handler(message):
    uid = str(message.from_user.id)
    
    if not check_sub(uid):
        bot.send_message(message.chat.id, "⚠️ **ДОСТУП ЗАБЛОКИРОВАН**\n\nДля использования бота подпишитесь на наш канал!", 
                         parse_mode="Markdown", reply_markup=sub_kb())
        return

    # Логика регистрации и рефералов
    user_data = supabase.table("users").select("*").eq("user_id", uid).execute()
    if not user_data.data:
        referrer = None
        args = message.text.split()
        if len(args) > 1: referrer = args[1]
        
        supabase.table("users").insert({
            "user_id": uid, 
            "first_name": message.from_user.first_name,
            "referrer_id": referrer,
            "balance": 0.0,
            "refs_count": 0
        }).execute()
        
        # Начисляем бонус пригласителю
        if referrer:
            r_res = supabase.table("users").select("balance, refs_count").eq("user_id", referrer).execute()
            if r_res.data:
                new_b = float(r_res.data[0]['balance'] or 0) + 0.50 # Даем 0.50$ за друга
                new_c = int(r_res.data[0]['refs_count'] or 0) + 1
                supabase.table("users").update({"balance": new_b, "refs_count": new_c}).eq("user_id", referrer).execute()
                try: bot.send_message(referrer, f"💎 Друг подписался! Вам начислено **0.50$**", parse_mode="Markdown")
                except: pass

    bot.send_message(message.chat.id, "🚀 **БОТ АКТИВИРОВАН**\nПриглашай друзей и зарабатывай реальные деньги.", 
                     reply_markup=main_kb(uid), parse_mode="Markdown")

# --- CALLBACKS ---
@bot.callback_query_handler(func=lambda call: True)
def calls(call):
    uid, cid = str(call.from_user.id), call.message.chat.id
    
    # Кнопка проверки подписки
    if call.data == "check_subscription":
        if check_sub(uid):
            bot.answer_callback_query(call.id, "✅ Подписка подтверждена!")
            start_handler(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ Вы всё еще не подписаны!", show_alert=True)
        return

    # Защита всех остальных кнопок
    if not check_sub(uid):
        bot.answer_callback_query(call.id, "🔒 Сначала подпишитесь на канал!", show_alert=True)
        return

    if call.data == "profile":
        u = supabase.table("users").select("*").eq("user_id", uid).execute().data[0]
        text = f"👤 **ПРОФИЛЬ**\n\n💰 Баланс: `{u['balance']}$`\n👥 Рефералы: `{u['refs_count']}`"
        bot.send_message(cid, text, parse_mode="Markdown")

    elif call.data == "ref":
        bot_name = bot.get_me().username
        bot.send_message(cid, f"🔗 **Твоя ссылка:**\n`https://t.me/{bot_name}?start={uid}`", parse_mode="Markdown")

    elif call.data == "admin_main" and uid == ADMIN_ID:
        akb = telebot.types.InlineKeyboardMarkup()
        akb.add(telebot.types.InlineKeyboardButton("📢 Рассылка", callback_data="adm_bc"))
        bot.send_message(cid, "🛠 **АДМИНКА**", reply_markup=akb)

    elif call.data == "adm_bc":
        user_state[uid] = 'bc'
        bot.send_message(cid, "✍️ Отправьте сообщение для рассылки:")

    bot.answer_callback_query(call.id)

# --- АДМИН-ТЕКСТ (РАССЫЛКА) ---
@bot.message_handler(func=lambda m: user_state.get(str(m.from_user.id)) == 'bc')
def do_bc(message):
    user_state[str(message.from_user.id)] = None
    users = supabase.table("users").select("user_id").execute()
    success = 0
    for u in users.data:
        try:
            bot.send_message(u['user_id'], message.text)
            success += 1
        except: pass
    bot.send_message(message.chat.id, f"✅ Рассылка окончена: {success} юзеров получили пост.")

# --- WEBHOOK ---
@app.route('/', methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200
