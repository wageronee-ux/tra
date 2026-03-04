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
        telebot.types.InlineKeyboardButton("🏆 ТОП 10", callback_data="top_list")
    )
    markup.add(
        telebot.types.InlineKeyboardButton("🔗 Ссылка", callback_data="ref_menu"),
        telebot.types.InlineKeyboardButton("💸 Вывод", callback_data="withdraw_money")
    )
    if user_id == ADMIN_ID:
        markup.add(telebot.types.InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_main"))
    return markup

def sub_keyboard():
    markup = telebot.types.InlineKeyboardMarkup()
    url_button = telebot.types.InlineKeyboardButton(text="Подписаться на канал", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")
    check_button = telebot.types.InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")
    markup.add(url_button)
    markup.add(check_button)
    return markup

def check_sub(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

# --- 3. ОБРАБОТЧИК START ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    if not check_sub(user_id):
        bot.send_message(message.chat.id, f"⚠️ Подпишись на {CHANNEL_ID}", reply_markup=sub_keyboard())
        return

    ref_id = None
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])
    if ref_id == user_id: ref_id = None

    try:
        # Фикс: используем str(user_id) для стабильности Supabase
        res = supabase.table("users").select("user_id").eq("user_id", str(user_id)).execute()
        if not res.data:
            supabase.table("users").insert({
                "user_id": user_id, 
                "username": message.from_user.username or "Unknown", 
                "first_name": message.from_user.first_name or "User",
                "referrer_id": ref_id, 
                "refs_count": 0, 
                "balance": 0
            }).execute()
            
            if ref_id:
                ref_res = supabase.table("users").select("refs_count", "balance").eq("user_id", str(ref_id)).execute()
                if ref_res.data:
                    supabase.table("users").update({
                        "refs_count": ref_res.data[0]['refs_count'] + 1, 
                        "balance": ref_res.data[0]['balance'] + 0.1
                    }).eq("user_id", str(ref_id)).execute()
        
        bot.send_message(message.chat.id, "🚀 Меню управления:", reply_markup=main_keyboard(user_id))
    except Exception as e:
        print(f"Error: {e}")
        bot.send_message(message.chat.id, "❌ Ошибка базы данных.")

# --- 4. ОБРАБОТКА КНОПОК ---
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    user_id = call.from_user.id
    # Обязательный ответ на Callback, чтобы кнопка не "висла"
    bot.answer_callback_query(call.id)

    if call.data == "check_subscription":
        if check_sub(user_id):
            bot.send_message(call.message.chat.id, "✅ Доступ открыт!", reply_markup=main_keyboard(user_id))
        else:
            bot.answer_callback_query(call.id, "❌ Ты не подписан!", show_alert=True)

    elif call.data == "profile":
        res = supabase.table("users").select("balance", "refs_count").eq("user_id", str(user_id)).execute()
        if res.data:
            d = res.data[0]
            text = f"👤 **ПРОФИЛЬ**\n\n💰 Баланс: `${d['balance']:.2f}`\n👥 Рефералов: `{d['refs_count']}`"
            bot.send_message(call.message.chat.id, text, reply_markup=main_keyboard(user_id), parse_mode="Markdown")

    elif call.data == "ref_menu":
        me = bot.get_me()
        link = f"https://t.me/{me.username}?start={user_id}"
        bot.send_message(call.message.chat.id, f"🔗 **Твоя ссылка:**\n`{link}`", reply_markup=main_keyboard(user_id), parse_mode="Markdown")

    elif call.data == "top_list":
        res = supabase.table("users").select("first_name", "refs_count").order("refs_count", desc=True).limit(10).execute()
        text = "🏆 **ТОП 10 ЛИДЕРОВ**\n\n"
        for i, u in enumerate(res.data, 1):
            m = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "👤"
            text += f"{m} {i}. {u['first_name']} — `{u['refs_count']}` чел.\n"
        bot.send_message(call.message.chat.id, text, reply_markup=main_keyboard(user_id), parse_mode="Markdown")

    elif call.data == "withdraw_money":
        res = supabase.table("users").select("balance").eq("user_id", str(user_id)).execute()
        bal = res.data[0]['balance'] if res.data else 0
        if bal < 5.0:
            bot.answer_callback_query(call.id, f"❌ Минимум $5.00", show_alert=True)
        else:
            bot.send_message(LOG_CHANNEL_ID, f"💸 ЗАЯВКА: {user_id} на ${bal:.2f}")
            bot.send_message(call.message.chat.id, "✅ Заявка отправлена!")

# --- 5. ВЕБХУК ---
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403
