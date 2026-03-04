import os
import time
import telebot
from flask import Flask, request
from supabase import create_client, Client

# --- КОНФИГ ---
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8040642138
CHANNEL_ID = "@traffchanel"
CHANNEL_LINK = "https://t.me/traffchanel"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Кэш подписок (uid: (status, timestamp))
sub_cache = {}
user_state = {}

def is_subscribed(uid):
    now = time.time()
    if uid in sub_cache and now - sub_cache[uid][1] < 60:
        return sub_cache[uid][0]
    
    try:
        status = bot.get_chat_member(CHANNEL_ID, uid).status
        is_sub = status in ['member', 'administrator', 'creator']
        sub_cache[uid] = (is_sub, now)
        return is_sub
    except:
        return False

def safe_answer(call_id, text=None, alert=False):
    try:
        bot.answer_callback_query(call_id, text=text, show_alert=alert)
    except:
        pass

# --- ГЛАВНОЕ МЕНЮ ---
def main_menu():
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("👤 Профиль", callback_data="p"),
        telebot.types.InlineKeyboardButton("🏆 ТОП", callback_data="t"),
        telebot.types.InlineKeyboardButton("🔗 Рефка", callback_data="r"),
        telebot.types.InlineKeyboardButton("💸 Вывод", callback_data="w")
    )
    return markup

@bot.message_handler(commands=['start'])
def start_cmd(m):
    uid = str(m.from_user.id)
    if not is_subscribed(uid):
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("📢 Подписаться", url=CHANNEL_LINK))
        kb.add(telebot.types.InlineKeyboardButton("✅ Проверить", callback_data="check"))
        return bot.send_message(m.chat.id, "❌ Доступ закрыт! Подпишись на канал:", reply_markup=kb)

    # Оптимизированная регистрация
    user = supabase.table("users").select("id").eq("user_id", uid).execute().data
    if not user:
        ref_id = m.text.split()[1] if len(m.text.split()) > 1 else None
        if ref_id == uid: ref_id = None
        
        supabase.table("users").insert({
            "user_id": uid, "first_name": m.from_user.first_name,
            "referrer_id": ref_id, "balance": 0, "refs_count": 0
        }).execute()
        
        if ref_id:
            # Обновление баланса пригласителя одним запросом
            supabase.rpc('increment_ref', {'row_id': ref_id}).execute() 
            # Примечание: RPC - это функция внутри Supabase. Если ее нет, используй стандартный update.
            try: bot.send_message(ref_id, "💎 +0.50$ за друга!")
            except: pass

    bot.send_message(m.chat.id, "🚀 Бот готов к работе!", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: True)
def handle_cb(c):
    uid, cid = str(c.from_user.id), c.message.chat.id
    
    if c.data == "check":
        if is_subscribed(uid):
            bot.edit_message_text("✅ Подписка подтверждена!", cid, c.message.message_id)
            return start_cmd(c.message)
        return safe_answer(c.id, "❌ Подписка не найдена!", True)

    if not is_subscribed(uid):
        return safe_answer(c.id, "❗ Сначала подпишись!", True)

    if c.data == "p":
        u = supabase.table("users").select("*").eq("user_id", uid).single().execute().data
        bot.send_message(cid, f"👤 **Профиль**\n\n💰 Баланс: `{u['balance']}$` \n👥 Рефералов: `{u['refs_count']}`", parse_mode="Markdown")
    
    elif c.data == "r":
        bot.send_message(cid, f"🔗 Ссылка: `https://t.me/{(bot.get_me().username)}?start={uid}`", parse_mode="Markdown")

    elif c.data == "t":
        top = supabase.table("users").select("first_name, refs_count").order("refs_count", desc=True).limit(5).execute().data
        txt = "🏆 **Лидеры:**\n" + "\n".join([f"{i+1}. {x['first_name']} — {x['refs_count']}" for i,x in enumerate(top)])
        bot.send_message(cid, txt, parse_mode="Markdown")

    elif c.data == "w":
        u = supabase.table("users").select("balance").eq("user_id", uid).single().execute().data
        if float(u['balance']) < 5:
            return safe_answer(c.id, "❌ Нужно минимум 5$", True)
        user_state[uid] = float(u['balance'])
        bot.send_message(cid, "📝 Введите ваш адрес для выплаты:")

    safe_answer(c.id)

@bot.message_handler(func=lambda m: str(m.from_user.id) in user_state)
def withdraw_finish(m):
    uid = str(m.from_user.id)
    amount = user_state.pop(uid)
    wallet = m.text
    
    # Атомарное списание
    supabase.table("users").update({"balance": 0}).eq("user_id", uid).execute()
    
    bot.send_message(ADMIN_ID, f"💰 **ВЫПЛАТА**\nЮзер: `{uid}`\nСумма: `{amount}$`\nКошелек: `{wallet}`", parse_mode="Markdown")
    bot.send_message(m.chat.id, "✅ Заявка ушла админу. Ожидайте.")

@app.route('/', methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "ok", 200
