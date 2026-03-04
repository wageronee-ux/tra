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
LOG_CHANNEL_ID = -1003850107854 # ID канала для заявок на выплату

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def check_sub(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def main_keyboard(user_id):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    btn_profile = telebot.types.InlineKeyboardButton("👤 Профиль", callback_data="profile")
    btn_top = telebot.types.InlineKeyboardButton("🏆 ТОП 10", callback_data="top_list")
    btn_ref = telebot.types.InlineKeyboardButton("🔗 Ссылка", callback_data="ref_menu")
    btn_withdraw = telebot.types.InlineKeyboardButton("💸 Вывод", callback_data="withdraw_money")
    
    # Кнопка для быстрой отправки ссылки другу
    btn_share = telebot.types.InlineKeyboardButton("🚀 Пригласить друга", switch_inline_query="Заходи и зарабатывай!")
    
    markup.add(btn_profile, btn_top)
    markup.add(btn_ref, btn_withdraw)
    markup.add(btn_share)
    
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

# --- 3. КОМАНДА START ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    first_name = message.from_user.first_name or "User"

    if not check_sub(user_id):
        bot.send_message(message.chat.id, f"⚠️ Для доступа подпишитесь на канал {CHANNEL_ID}", reply_markup=sub_keyboard())
        return

    ref_id = None
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])
    if ref_id == user_id: ref_id = None

    try:
        res = supabase.table("users").select("user_id").eq("user_id", user_id).execute()
        if not res.data:
            supabase.table("users").insert({
                "user_id": user_id, "username": username, "first_name": first_name,
                "referrer_id": ref_id, "refs_count": 0, "balance": 0
            }).execute()
            
            if ref_id:
                ref_res = supabase.table("users").select("refs_count", "balance").eq("user_id", ref_id).execute()
                if ref_res.data:
                    new_count = (ref_res.data[0].get("refs_count") or 0) + 1
                    new_balance = (ref_res.data[0].get("balance") or 0) + 0.1 # Цена за рефа
                    supabase.table("users").update({"refs_count": new_count, "balance": new_balance}).eq("user_id", ref_id).execute()
                    try: bot.send_message(ref_id, "🔔 +$0.10 за нового друга!")
                    except: pass
            
            bot.send_message(message.chat.id, f"🚀 Привет, {first_name}! Ты успешно в игре.", reply_markup=main_keyboard(user_id))
        else:
            bot.send_message(message.chat.id, "🚀 Главное меню:", reply_markup=main_keyboard(user_id))
    except:
        bot.reply_to(message, "⚠️ Ошибка базы данных.")

# --- 4. ОБРАБОТКА КНОПОК ---
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    user_id = call.from_user.id

    if call.data == "check_subscription":
        if check_sub(user_id):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, "✅ Доступ открыт! Жми /start", reply_markup=main_keyboard(user_id))
        else:
            bot.answer_callback_query(call.id, "❌ Подписка не найдена!", show_alert=True)

    elif call.data == "profile":
        res = supabase.table("users").select("balance", "refs_count").eq("user_id", user_id).execute()
        if res.data:
            data = res.data[0]
            text = f"👤 **ПРОФИЛЬ**\n\n💰 Баланс: `${data.get('balance', 0):.2f}`\n👥 Рефералов: `{data.get('refs_count', 0)}`"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=main_keyboard(user_id), parse_mode="Markdown")

    elif call.data == "ref_menu":
        bot_info = bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={user_id}"
        text = f"🔗 **Твоя ссылка:**\n`{link}`\n\nПриглашай друзей и зарабатывай!"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=main_keyboard(user_id), parse_mode="Markdown")

    elif call.data == "top_list":
        res = supabase.table("users").select("first_name", "refs_count").order("refs_count", desc=True).limit(10).execute()
        text = "🏆 **ТОП 10 ЛИДЕРОВ**\n\n"
        for i, user in enumerate(res.data, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "👤"
            text += f"{medal} {i}. {user['first_name']} — `{user['refs_count']}` чел.\n"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=main_keyboard(user_id), parse_mode="Markdown")

    elif call.data == "withdraw_money":
        res = supabase.table("users").select("balance", "first_name").eq("user_id", user_id).execute()
        balance = res.data[0].get("balance", 0) if res.data else 0
        if balance < 5.0: # Минимум 5 баксов
            bot.answer_callback_query(call.id, f"❌ Минимум для вывода $5.00 (у тебя ${balance:.2f})", show_alert=True)
        else:
            bot.send_message(LOG_CHANNEL_ID, f"💸 **ЗАЯВКА НА ВЫВОД**\nЮзер: {res.data[0]['first_name']} (`{user_id}`)\nСумма: ${balance:.2f}")
            bot.answer_callback_query(call.id, "✅ Заявка отправлена!", show_alert=True)

    elif call.data == "admin_main" and user_id == ADMIN_ID:
        res = supabase.table("users").select("user_id", count="exact").execute()
        bot.edit_message_text(f"⚙️ **Админка**\nЮзеров: {res.count}", call.message.chat.id, call.message.message_id, 
                              reply_markup=telebot.types.InlineKeyboardMarkup().add(telebot.types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")))

    elif call.data == "admin_broadcast" and user_id == ADMIN_ID:
        bot.send_message(call.message.chat.id, "Введите текст рассылки в ответ на это сообщение.")

# --- 5. ВЕБХУК ---
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403
