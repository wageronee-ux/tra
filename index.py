import os
import telebot
from flask import Flask, request
from supabase import create_client, Client

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_ID = 8040642138 # Твой ID (числом)
CHANNEL_ID = "@твой_канал" 
CHANNEL_LINK = "https://t.me/твой_канал"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

user_state = {}

# --- УТИЛИТЫ ---
def is_subscribed(uid):
    try:
        status = bot.get_chat_member(CHANNEL_ID, uid).status
        return status in ['member', 'administrator', 'creator']
    except Exception:
        return False

def safe_answer(call_id, text=None, show_alert=False):
    try:
        bot.answer_callback_query(call_id, text=text, show_alert=show_alert)
    except Exception as e:
        print(f"Callback error (ignore): {e}")

def get_main_kb():
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        telebot.types.InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        telebot.types.InlineKeyboardButton("🏆 ТОП", callback_data="top"),
        telebot.types.InlineKeyboardButton("🔗 Реф. ссылка", callback_data="ref"),
        telebot.types.InlineKeyboardButton("💸 Вывод", callback_data="withdraw")
    )
    return kb

# --- АДМИН-ФУНКЦИИ ---
@bot.message_handler(commands=['send'], func=lambda m: m.from_user.id == ADMIN_ID)
def broadcast(message):
    text = message.text.replace("/send ", "")
    users = supabase.table("users").select("user_id").execute()
    count = 0
    for u in users.data:
        try:
            bot.send_message(u['user_id'], text)
            count += 1
        except: continue
    bot.send_message(ADMIN_ID, f"✅ Рассылка завершена. Получили: {count} чел.")

# --- ОБРАБОТКА КОМАНД ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    
    if not is_subscribed(uid):
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("📢 Подписаться", url=CHANNEL_LINK))
        kb.add(telebot.types.InlineKeyboardButton("✅ Проверить подписку", callback_data="check_sub"))
        bot.send_message(message.chat.id, "❗ Подпишитесь на канал, чтобы продолжить:", reply_markup=kb)
        return

    # Регистрация пользователя
    res = supabase.table("users").select("*").eq("user_id", uid).execute()
    if not res.data:
        ref_id = message.text.split()[1] if len(message.text.split()) > 1 else None
        if ref_id == uid: ref_id = None
        
        supabase.table("users").insert({
            "user_id": uid, "first_name": message.from_user.first_name,
            "referrer_id": ref_id, "balance": 0.0, "refs_count": 0
        }).execute()
        
        if ref_id:
            r_data = supabase.table("users").select("balance, refs_count").eq("user_id", ref_id).execute()
            if r_data.data:
                new_bal = float(r_data.data[0]['balance'] or 0) + 0.50
                new_cnt = int(r_data.data[0]['refs_count'] or 0) + 1
                supabase.table("users").update({"balance": new_bal, "refs_count": new_cnt}).eq("user_id", ref_id).execute()
                try: bot.send_message(ref_id, "💎 +0.50$ за нового друга!")
                except: pass

    bot.send_message(message.chat.id, "💎 Добро пожаловать! Выбирай раздел:", reply_markup=get_main_kb())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid, cid = str(call.from_user.id), call.message.chat.id

    if call.data == "check_sub":
        if is_subscribed(uid):
            safe_answer(call.id, "✅ Спасибо за подписку!")
            start(call.message)
        else:
            safe_answer(call.id, "❌ Вы всё еще не подписаны!", show_alert=True)
        return

    # Для остальных кнопок тоже проверяем подписку "на лету"
    if not is_subscribed(uid):
        safe_answer(call.id, "❗ Сначала подпишитесь на канал!", show_alert=True)
        return

    if call.data == "profile":
        u = supabase.table("users").select("*").eq("user_id", uid).execute().data[0]
        bot.send_message(cid, f"👤 **Имя:** {u['first_name']}\n💰 **Баланс:** `{u['balance']}$`\n👥 **Рефералов:** {u['refs_count']}", parse_mode="Markdown")
    
    elif call.data == "top":
        top = supabase.table("users").select("first_name, refs_count").order("refs_count", desc=True).limit(10).execute()
        text = "🏆 **ТОП пригласителей:**\n\n"
        for i, user in enumerate(top.data, 1):
            text += f"{i}. {user['first_name']} — {user['refs_count']} чел.\n"
        bot.send_message(cid, text, parse_mode="Markdown")

    elif call.data == "ref":
        me = bot.get_me().username
        bot.send_message(cid, f"🔗 Твоя ссылка:\n`https://t.me/{me}?start={uid}`", parse_mode="Markdown")

    elif call.data == "withdraw":
        u = supabase.table("users").select("balance").eq("user_id", uid).execute().data[0]
        if float(u['balance']) < 1.5:
            safe_answer(call.id, "❌ Минимум 5$ для вывода", show_alert=True)
        else:
            user_state[uid] = 'wait_wallet'
            bot.send_message(cid, "Введите ваш кошелек (TRC20/Card/etc):")

    safe_answer(call.id)

@bot.message_handler(func=lambda m: user_state.get(str(m.from_user.id)) == 'wait_wallet')
def process_withdrawal(message):
    uid = str(message.from_user.id)
    wallet = message.text
    user_state[uid] = None
    bot.send_message(ADMIN_ID, f"💰 **ВЫВОД**\nID: `{uid}`\nРеквизиты: `{wallet}`", parse_mode="Markdown")
    bot.send_message(message.chat.id, "✅ Заявка отправлена админу.")

# --- WEBHOOK ---
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    return 'Forbidden', 403
