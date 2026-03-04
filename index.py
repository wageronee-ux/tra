import os
import telebot
from flask import Flask, request
from supabase import create_client, Client

# Конфигурация
TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_ID = 8040642138  

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# ⌨️ КРАСИВОЕ ГЛАВНОЕ МЕНЮ (REPLY)
# ==========================================
def main_menu_keyboard(user_id):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    # Кнопки с эмодзи для красоты
    btn_profile = telebot.types.KeyboardButton("👤 Мой профиль")
    btn_top = telebot.types.KeyboardButton("🏆 ТОП лидеров")
    btn_ref = telebot.types.KeyboardButton("🔗 Реф. ссылка")
    btn_withdraw = telebot.types.KeyboardButton("💸 Вывести $")
    
    markup.add(btn_profile)
    markup.add(btn_top, btn_ref)
    markup.add(btn_withdraw)
    
    if user_id == ADMIN_ID:
        markup.add(telebot.types.KeyboardButton("⚙️ Админ-панель"))
    return markup

# ==========================================
# 🚀 ОБРАБОТЧИКИ КОМАНД
# ==========================================

@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    try:
        # Проверка/Регистрация пользователя (всегда приводим uid к str)
        res = supabase.table("users").select("user_id").eq("user_id", uid).execute()
        
        if not res.data:
            ref_id = None
            args = message.text.split()
            if len(args) > 1 and args[1].isdigit() and args[1] != uid:
                ref_id = args[1]
            
            supabase.table("users").insert({
                "user_id": uid, 
                "username": message.from_user.username or "none",
                "first_name": message.from_user.first_name or "Пользователь",
                "referrer_id": ref_id,
                "balance": 0.0,
                "refs_count": 0
            }).execute()
            
            if ref_id:
                r_res = supabase.table("users").select("balance", "refs_count").eq("user_id", str(ref_id)).execute()
                if r_res.data:
                    new_bal = float(r_res.data[0]['balance']) + 0.1
                    new_count = int(r_res.data[0]['refs_count']) + 1
                    supabase.table("users").update({"balance": new_bal, "refs_count": new_count}).eq("user_id", str(ref_id)).execute()

        welcome_text = (
            f"👋 **Привет, {message.from_user.first_name}!**\n"
            f"────────────────────\n"
            f"Добро пожаловать в нашу систему!\n"
            f"Используй кнопки ниже для управления."
        )
        bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=main_menu_keyboard(message.from_user.id))
    except Exception as e:
        print(f"Error: {e}")

# ==========================================
# 📝 ОБРАБОТКА ТЕКСТОВЫХ КНОПОК
# ==========================================

@bot.message_handler(func=lambda message: True)
def handle_text_menu(message):
    uid = str(message.from_user.id)
    chat_id = message.chat.id

    if message.text == "👤 Мой профиль":
        res = supabase.table("users").select("balance", "refs_count").eq("user_id", uid).execute()
        if res.data:
            data = res.data[0]
            profile_text = (
                f"👤 **ВАШ ПРОФИЛЬ**\n"
                f"────────────────────\n"
                f"💰 **Баланс:** `{data['balance']}$` \n"
                f"👥 **Рефералы:** `{data['refs_count']}` чел.\n"
                f"────────────────────\n"
                f"💳 Статус: **Активен**"
            )
            bot.send_message(chat_id, profile_text, parse_mode="Markdown")

    elif message.text == "🔗 Реф. ссылка":
        bot_info = bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={uid}"
        ref_text = (
            f"🔗 **ПАРТНЕРСКАЯ ССЫЛКА**\n"
            f"────────────────────\n"
            f"Приглашай друзей и получай бонусы!\n\n"
            f"Твоя ссылка:\n`{link}`"
        )
        bot.send_message(chat_id, ref_text, parse_mode="Markdown")

    elif message.text == "🏆 ТОП лидеров":
        res = supabase.table("users").select("first_name", "refs_count").order("refs_count", desc=True).limit(10).execute()
        top_text = "🏆 **ТОП 10 ПРИГЛАСИТЕЛЕЙ**\n"
        top_text += "────────────────────\n"
        for i, u in enumerate(res.data, 1):
            top_text += f"{i}. {u['first_name']} — `{u['refs_count']}` чел.\n"
        bot.send_message(chat_id, top_text, parse_mode="Markdown")

    elif message.text == "💸 Вывести $":
        res = supabase.table("users").select("balance").eq("user_id", uid).execute()
        balance = res.data[0]['balance'] if res.data else 0
        withdraw_text = (
            f"💸 **ВЫВОД СРЕДСТВ**\n"
            f"────────────────────\n"
            f"Твой баланс: `{balance}$`\n"
            f"Минимальная сумма: `10$`\n\n"
            f"❌ Недостаточно средств для вывода."
        )
        bot.send_message(chat_id, withdraw_text, parse_mode="Markdown")

# ==========================================
# WEBHOOK ЧАСТЬ
# ==========================================

@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403
