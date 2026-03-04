import os
import telebot
from flask import Flask, request
from supabase import create_client, Client

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_ID = "8040642138" 
CHANNEL_ID = "@traffchanel" 
CHANNEL_LINK = "https://t.me/traffchanel"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

user_state = {}

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def is_subscribed(uid):
    try:
        status = bot.get_chat_member(CHANNEL_ID, uid).status
        return status in ['member', 'administrator', 'creator']
    except Exception:
        return False

def get_main_kb(uid):
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        telebot.types.InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        telebot.types.InlineKeyboardButton("🏆 ТОП Лидеров", callback_data="top")
    )
    kb.add(
        telebot.types.InlineKeyboardButton("🔗 Реф. ссылка", callback_data="ref"),
        telebot.types.InlineKeyboardButton("💸 Вывод", callback_data="withdraw")
    )
    return kb

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    
    if not is_subscribed(uid):
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("📢 Подписаться", url=CHANNEL_LINK))
        kb.add(telebot.types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
        bot.send_message(message.chat.id, "❗ Для использования бота нужна подписка на канал.", reply_markup=kb)
        return

    # Регистрация
    res = supabase.table("users").select("*").eq("user_id", uid).execute()
    if not res.data:
        ref_id = message.text.split()[1] if len(message.text.split()) > 1 else None
        # Проверяем, чтобы не пригласил сам себя
        if ref_id == uid: ref_id = None
        
        supabase.table("users").insert({
            "user_id": uid, "first_name": message.from_user.first_name,
            "referrer_id": ref_id, "balance": 0.0, "refs_count": 0
        }).execute()
        
        if ref_id:
            # Начисляем бонус пригласителю
            r_data = supabase.table("users").select("balance, refs_count").eq("user_id", ref_id).execute()
            if r_data.data:
                new_bal = float(r_data.data[0]['balance'] or 0) + 0.50
                new_cnt = int(r_data.data[0]['refs_count'] or 0) + 1
                supabase.table("users").update({"balance": new_bal, "refs_count": new_cnt}).eq("user_id", ref_id).execute()
                try: bot.send_message(ref_id, f"💎 Новый реферал! +0.50$ на баланс.")
                except: pass

    bot.send_message(message.chat.id, f"🏠 Главное меню", reply_markup=get_main_kb(uid))

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid, cid = str(call.from_user.id), call.message.chat.id

    if call.data == "profile":
        u = supabase.table("users").select("*").eq("user_id", uid).execute().data[0]
        text = (f"👤 **Профиль:** {u['first_name']}\n"
                f"💰 **Баланс:** `{u['balance']}$` (Мин. вывод: 5$)\n"
                f"👥 **Рефералов:** {u['refs_count']}")
        bot.send_message(cid, text, parse_mode="Markdown")

    elif call.data == "top":
        # Берем ТОП-10 по количеству рефералов
        top_users = supabase.table("users").select("first_name, refs_count").order("refs_count", desc=True).limit(10).execute()
        text = "🏆 **ТОП-10 ПРИГЛАСИТЕЛЕЙ:**\n\n"
        for i, user in enumerate(top_users.data, 1):
            text += f"{i}. {user['first_name']} — {user['refs_count']} чел.\n"
        bot.send_message(cid, text, parse_mode="Markdown")

    elif call.data == "ref":
        bot_user = bot.get_me().username
        link = f"https://t.me/{bot_user}?start={uid}"
        bot.send_message(cid, f"🎁 Приглашай друзей и получай **0.50$** за каждого!\n\n🔗 Твоя ссылка:\n`{link}`", parse_mode="Markdown")

    elif call.data == "withdraw":
        u = supabase.table("users").select("balance").eq("user_id", uid).execute().data[0]
        if float(u['balance']) < 5.0:
            bot.answer_callback_query(call.id, "❌ Недостаточно средств (минимум 5$)", show_alert=True)
        else:
            user_state[uid] = 'waiting_wallet'
            bot.send_message(cid, "💳 Введите номер кошелька или карты для выплаты:")

    elif call.data == "check_sub":
        if is_subscribed(uid):
            bot.answer_callback_query(call.id, "✅ Подписка подтверждена!")
            start(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ Вы всё еще не подписаны", show_alert=True)

    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda m: user_state.get(str(m.from_user.id)) == 'waiting_wallet')
def process_wallet(message):
    uid = str(message.from_user.id)
    wallet = message.text
    user_state[uid] = None
    
    # Уведомление админу
    bot.send_message(ADMIN_ID, f"🚨 **ЗАЯВКА НА ВЫВОД**\nЮзер: `{uid}`\nРеквизиты: `{wallet}`", parse_mode="Markdown")
    bot.send_message(message.chat.id, "✅ Заявка принята! Ожидайте выплаты.")

# --- WEBHOOK ---
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return "Forbidden", 403
