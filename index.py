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

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (ПОДПИСКА) ---
def check_sub(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        return False
    except Exception:
        return False

def sub_keyboard():
    markup = telebot.types.InlineKeyboardMarkup()
    url_button = telebot.types.InlineKeyboardButton(text="Подписаться на канал", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")
    check_button = telebot.types.InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")
    markup.add(url_button)
    markup.add(check_button)
    return markup

# --- 3. КОМАНДА START (РЕГИСТРАЦИЯ) ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    first_name = message.from_user.first_name or "User"

    # Проверка подписки
    if not check_sub(user_id):
        bot.send_message(message.chat.id, f"Для использования бота нужно подписаться на наш канал {CHANNEL_ID}!", 
                         reply_markup=sub_keyboard())
        return

    # Логика рефералов
    ref_id = None
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])
    if ref_id == user_id: ref_id = None

    try:
        res = supabase.table("users").select("user_id").eq("user_id", user_id).execute()
        
        if not res.data:
            # Новый юзер
            supabase.table("users").insert({
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "referrer_id": ref_id,
                "refs_count": 0
            }).execute()
            
            if ref_id:
                ref_res = supabase.table("users").select("refs_count").eq("user_id", ref_id).execute()
                if ref_res.data:
                    old_count = ref_res.data[0].get("refs_count") or 0
                    supabase.table("users").update({"refs_count": old_count + 1}).eq("user_id", ref_id).execute()
            
            bot.reply_to(message, f"✨ Привет, {first_name}! Ты успешно зарегистрирован.")
        else:
            bot.reply_to(message, "Ты уже в игре! Используй меню для навигации.")
            
    except Exception as e:
        bot.reply_to(message, "⚠️ Ошибка базы данных.")

# --- 4. КОМАНДА ADMIN ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return 

    try:
        res = supabase.table("users").select("user_id", count="exact").execute()
        total_users = res.count if res.count is not None else 0
        
        markup = telebot.types.InlineKeyboardMarkup()
        btn1 = telebot.types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")
        btn2 = telebot.types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")
        markup.add(btn1, btn2)
        
        bot.send_message(message.chat.id, f"🛠 **Админ-панель**\n\nЮзеров в базе: {total_users}", 
                         parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")

# --- 5. КОМАНДА REF ---
@bot.message_handler(commands=['ref', 'referral'])
def referral_menu(message):
    user_id = message.from_user.id
    try:
        bot_info = bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        res = supabase.table("users").select("refs_count").eq("user_id", user_id).execute()
        
        count = res.data[0].get("refs_count", 0) if res.data else 0
        text = f"👥 *Реферальное меню*\n\n🔗 Ссылка:\n`{ref_link}`\n\n📊 Друзей: *{count}*"
        bot.send_message(message.chat.id, text, parse_mode="Markdown")
    except:
        bot.send_message(message.chat.id, "⚠️ Ошибка.")

# --- 6. ОБРАБОТКА КНОПОК ---
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.data == "check_subscription":
        if check_sub(call.from_user.id):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, "✅ Подписка подтверждена! Жми /start")
        else:
            bot.answer_callback_query(call.id, "❌ Ты всё еще не подписан!", show_alert=True)
            
    elif call.data == "admin_broadcast":
        if call.from_user.id == ADMIN_ID:
            bot.send_message(call.message.chat.id, "Функция рассылки скоро будет готова!")

# --- 7. ВЕБХУК ---
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403
