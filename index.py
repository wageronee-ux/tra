import os
import telebot
from flask import Flask, request
from supabase import create_client, Client

# Конфигурация
TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_ID = 8040642138  # ЗАМЕНИ на свой Telegram ID
CHANNEL_ID = "@traffchanel" # ЗАМЕНИ на юзернейм своего канала

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# Подключаемся к Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def check_sub(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        return False
    except Exception:
        return False

# Клавиатура с кнопкой подписки
def sub_keyboard():
    markup = telebot.types.InlineKeyboardMarkup()
    url_button = telebot.types.InlineKeyboardButton(text="Подписаться на канал", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")
    check_button = telebot.types.InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")
    markup.add(url_button)
    markup.add(check_button)
    return markup
    
# --- КОМАНДА START ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    first_name = message.from_user.first_name or "User"

    # --- КОМАНДА admin ---
    @bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return # Игнорируем, если не админ

    try:
        # Считаем общее кол-во юзеров в базе
        res = supabase.table("users").select("user_id", count="exact").execute()
        total_users = res.count if res.count is not None else 0
        
        markup = telebot.types.InlineKeyboardMarkup()
        btn1 = telebot.types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")
        btn2 = telebot.types.InlineKeyboardButton("📊 Обновить БД", callback_data="admin_db_refresh")
        markup.add(btn1, btn2)
        
        bot.send_message(message.chat.id, f"🛠 **Панель администратора**\n\nВсего пользователей в базе: {total_users}", 
                         parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка админки: {e}")

    #---оброботка кнопок---
    @bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    
    # ПРОВЕРКА ПОДПИСКИ
    if not check_sub(user_id):
        bot.send_message(message.chat.id, f"Для использования бота нужно подписаться на наш канал {CHANNEL_ID}!", 
                         reply_markup=sub_keyboard())
        return

    # Далее идет твой старый код регистрации (проверка в Supabase и т.д.)
    # ... (код из предыдущего шага)
        
    # Реферальный ID из ссылки
    ref_id = None
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])
    
    # Нельзя пригласить самого себя
    if ref_id == user_id: 
        ref_id = None

    try:
        # Проверяем, есть ли уже такой пользователь
        res = supabase.table("users").select("user_id").eq("user_id", user_id).execute()
        
        if not res.data:
            # Создаем нового пользователя
            supabase.table("users").insert({
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "referrer_id": ref_id,
                "refs_count": 0
            }).execute()
            
            # Если есть реферер, прибавляем ему +1
            if ref_id:
                ref_res = supabase.table("users").select("refs_count").eq("user_id", ref_id).execute()
                if ref_res.data:
                    old_count = ref_res.data[0].get("refs_count") or 0
                    supabase.table("users").update({"refs_count": old_count + 1}).eq("user_id", ref_id).execute()
            
            bot.reply_to(message, f"✨ Привет, {first_name}! Ты успешно зарегистрирован.")
        else:
            bot.reply_to(message, "Ты уже в игре! Используй /ref для просмотра приглашенных.")
            
    except Exception as e:
        print(f"Supabase Error: {e}")
        bot.reply_to(message, "⚠️ Ошибка базы данных. Попробуй позже.")

# --- КОМАНДА REF (РЕФЕРАЛЬНОЕ МЕНЮ) ---
@bot.message_handler(commands=['ref', 'referral'])
def referral_menu(message):
    user_id = message.from_user.id
    
    try:
        # Получаем данные о боте для ссылки
        bot_info = bot.get_me()
        bot_username = bot_info.username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        
        # Берем количество рефералов из базы
        res = supabase.table("users").select("refs_count").eq("user_id", user_id).execute()
        
        if res.data:
            count = res.data[0].get("refs_count", 0)
            text = (
                f"👥 *Реферальное меню*\n\n"
                f"🔗 Твоя ссылка для приглашения:\n`{ref_link}`\n\n"
                f"📊 Приглашено друзей: *{count}*"
            )
            bot.send_message(message.chat.id, text, parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, "❌ Сначала введи /start")
            
    except Exception as e:
        print(f"Error in ref menu: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка базы данных.")

#---Обработка нажатий на кнопки---
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.data == "check_subscription":
        if check_sub(call.from_user.id):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, "✅ Спасибо! Теперь введи /start снова.")
        else:
            bot.answer_callback_query(call.id, "❌ Ты всё еще не подписан!", show_alert=True)
            
    elif call.data == "admin_broadcast":
        if call.from_user.id == ADMIN_ID:
            bot.send_message(call.message.chat.id, "Введите текст для рассылки (функция в разработке)")
            
# --- ВЕБХУК ДЛЯ VERCEL ---
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 4033

