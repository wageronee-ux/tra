import os
import telebot
from flask import Flask, request
from supabase import create_client, Client

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_ID = "8040642138"  # Всегда используем строку!

# Ссылка или file_id для главного GIF (пример)
WELCOME_GIF = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM2MzY2VhYzhkNGRkNGRmOGZkMTM4NWNhZDBkZjk4ZjFkMDhmNmRlNyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3o7TKSjRrfIPJeiT4s/giphy.gif"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- ГЛАВНОЕ МЕНЮ (INLINE) ---
def main_keyboard(user_id):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    # Используем красивые эмодзи
    markup.add(
        telebot.types.InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        telebot.types.InlineKeyboardButton("🏆 ТОП лидеров", callback_data="top")
    )
    markup.add(
        telebot.types.InlineKeyboardButton("🔗 Ссылка", callback_data="ref_link"),
        telebot.types.InlineKeyboardButton("💸 Вывод $", callback_data="withdraw")
    )
    # Кнопка админа (строгое сравнение строк)
    if str(user_id) == ADMIN_ID:
        markup.add(telebot.types.InlineKeyboardButton("⚙️ Админ Меню", callback_data="admin_menu"))
    return markup

# --- ОБРАБОТЧИК /START ---
@bot.message_handler(commands=['start'])
def start_command(message):
    uid = str(message.from_user.id)
    try:
        # Проверяем пользователя (всегда строку uid)
        check = supabase.table("users").select("user_id").eq("user_id", uid).execute()
        
        if not check.data:
            referrer = None
            args = message.text.split()
            if len(args) > 1 and args[1] != uid:
                referrer = str(args[1])

            supabase.table("users").insert({
                "user_id": uid,
                "username": message.from_user.username or "NoUser",
                "first_name": message.from_user.first_name,
                "balance": 0.0,
                "refs_count": 0,
                "referrer_id": referrer
            }).execute()

            if referrer:
                r_data = supabase.table("users").select("balance", "refs_count").eq("user_id", referrer).execute()
                if r_data.data:
                    new_bal = float(r_data.data[0]['balance']) + 0.1
                    new_cnt = int(r_data.data[0]['refs_count']) + 1
                    supabase.table("users").update({"balance": new_bal, "refs_count": new_cnt}).eq("user_id", referrer).execute()

        # Дизайн: Отправляем GIF при приветствии
        bot.send_animation(
            message.chat.id, 
            WELCOME_GIF,
            caption=f"👋 **Привет, {message.from_user.first_name}!**\n───────────────────\n"
                    f"Добро пожаловать в нашу партнерскую сеть.\n"
                    f"Приглашай друзей и зарабатывай!",
            parse_mode="Markdown",
            reply_markup=main_keyboard(uid)
        )
    except Exception as e:
        print(f"Start Error: {e}")

# --- ОБРАБОТКА CALLBACK ЗАПРОСОВ (НАЖАТИЯ КНОПОК) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_queries(call):
    uid = str(call.from_user.id)
    chat_id = call.message.chat.id

    try:
        # 👤 ПРОФИЛЬ
        if call.data == "profile":
            res = supabase.table("users").select("balance, refs_count").eq("user_id", uid).execute()
            if res.data:
                data = res.data[0]
                text = (
                    f"👤 **ВАШ ПРОФИЛЬ**\n"
                    f"────────────────────\n"
                    f"💳 Статус: **Активен**\n"
                    f"💰 Баланс: `{data['balance']}$` \n"
                    f"👥 Рефералы: `{data['refs_count']}` чел."
                )
                bot.send_message(chat_id, text, parse_mode="Markdown")

        # 🏆 ТОП 10
        elif call.data == "top":
            res = supabase.table("users").select("first_name, refs_count").order("refs_count", desc=True).limit(10).execute()
            top_text = "🏆 **ТОП 10 ПРИГЛАСИТЕЛЕЙ**\n\n"
            for i, u in enumerate(res.data, 1):
                top_text += f"{i}. {u['first_name']} — `{u['refs_count']}` реф.\n"
            bot.send_message(chat_id, top_text, parse_mode="Markdown")

        # 🔗 ССЫЛКА
        elif call.data == "ref_link":
            bot_name = bot.get_me().username
            link = f"https://t.me/{bot_name}?start={uid}"
            bot.send_message(chat_id, f"🔗 **Ваша ссылка:**\n`{link}`", parse_mode="Markdown")

        # 💸 ВЫВОД
        elif call.data == "withdraw":
            bot.send_message(chat_id, "❌ **Ошибка**\nМинимальный вывод: `10$`")

        # ⚙️ АДМИН МЕНЮ
        elif call.data == "admin_menu":
            if uid == ADMIN_ID:
                markup = telebot.types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    telebot.types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
                    telebot.types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
                    telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="main_menu")
                )
                bot.send_message(chat_id, "🛠 **ПАНЕЛЬ АДМИНИСТРАТОРА**", reply_markup=markup, parse_mode="Markdown")

        # Обработка подменю админа (примеры)
        elif call.data == "admin_stats":
            count = supabase.table("users").select("user_id", count="exact").execute()
            bot.send_message(chat_id, f"📊 Всего пользователей: `{count.count}`", parse_mode="Markdown")
        
        elif call.data == "admin_broadcast":
            bot.send_message(chat_id, "ℹ️ Функция рассылки пока в разработке.")

        elif call.data == "main_menu":
            # Возврат в главное меню
            bot.send_animation(chat_id, WELCOME_GIF, caption="Выберите раздел:", reply_markup=main_keyboard(uid))

        # Обязательно отвечаем Telegram!
        bot.answer_callback_query(call.id)

    except Exception as e:
        print(f"Callback Error: {e}")

# --- WEBHOOK ЧАСТЬ (FLASK) ---
@app.route('/', methods=['POST'])
def webhook_handler():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403
