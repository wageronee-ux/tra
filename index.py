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

user_state = {}

# --- КЛАВИАТУРЫ ---
def get_main_menu():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        telebot.types.KeyboardButton("🚀 Заработать"),
        telebot.types.KeyboardButton("👤 Мой Профиль"),
        telebot.types.KeyboardButton("🏆 Топ Лидеров"),
        telebot.types.KeyboardButton("💳 Вывод")
    )
    return markup

def get_sub_inline():
    # Ссылку на канал можно дать только через Inline
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("➕ Подписаться на канал", url=CHANNEL_LINK))
    return kb

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def check_sub(uid):
    try:
        status = bot.get_chat_member(CHANNEL_ID, uid).status
        return status in ['member', 'administrator', 'creator']
    except: return False

def get_user(uid):
    # Исправляем 400 Bad Request: приводим к числу, если нужно
    res = supabase.table("users").select("*").eq("user_id", str(uid)).execute()
    return res.data[0] if res.data else None

# --- КОМАНДЫ ---
@bot.message_handler(commands=['start'])
def send_welcome(m):
    uid = str(m.from_user.id)
    
    if not check_sub(uid):
        return bot.send_message(m.chat.id, "👋 **Добро пожаловать!**\n\nЧтобы начать зарабатывать, подпишись на наш официальный канал:", 
                                reply_markup=get_sub_inline(), parse_mode="Markdown")

    if not get_user(uid):
        # Регистрация с рефералкой
        ref_id = m.text.split()[1] if len(m.text.split()) > 1 else None
        supabase.table("users").insert({
            "user_id": uid, "first_name": m.from_user.first_name,
            "balance": 0, "refs_count": 0, "referrer_id": ref_id
        }).execute()
        
        if ref_id and ref_id != uid:
            # Начисление за друга (атомарное обновление в коде)
            ref_user = get_user(ref_id)
            if ref_user:
                new_bal = float(ref_user['balance']) + 0.50
                new_cnt = int(ref_user['refs_count']) + 1
                supabase.table("users").update({"balance": new_bal, "refs_count": new_cnt}).eq("user_id", ref_id).execute()
                try: bot.send_message(ref_id, f"💎 **+0.50$** за нового друга!")
                except: pass

    bot.send_message(m.chat.id, "✅ **Вы успешно авторизованы!**", reply_markup=get_main_menu(), parse_mode="Markdown")

# --- ОБРАБОТКА КНОПОК ---
@bot.message_handler(func=lambda m: True)
def handle_menu(m):
    uid = str(m.from_user.id)
    
    # Логика ввода кошелька
    if user_state.get(uid) == 'wait_wallet':
        u = get_user(uid)
        amount = u['balance']
        supabase.table("users").update({"balance": 0}).eq("user_id", uid).execute()
        
        bot.send_message(ADMIN_ID, f"🔔 **НОВЫЙ ВЫВОД**\nЮзер: `{uid}`\nСумма: `{amount}$`\nКошелек: `{m.text}`", parse_mode="Markdown")
        user_state[uid] = None
        return bot.send_message(m.chat.id, "💸 **Заявка отправлена!**\nСредства придут в течение 24 часов.", reply_markup=get_main_menu(), parse_mode="Markdown")

    if not check_sub(uid):
        return bot.send_message(m.chat.id, "❗ Сначала подпишись на канал!", reply_markup=get_sub_inline())

    if m.text == "👤 Мой Профиль":
        u = get_user(uid)
        text = (f"─── ✨ **ВАШ ПРОФИЛЬ** ✨ ───\n\n"
                f"👤 Имя: `{u['first_name']}`\n"
                f"💰 Баланс: `{u['balance']}$`\n"
                f"👥 Рефералов: `{u['refs_count']}`\n\n"
                f"────────────────────")
        bot.send_message(m.chat.id, text, parse_mode="Markdown")

    elif m.text == "🚀 Заработать":
        link = f"https://t.me/{bot.get_me().username}?start={uid}"
        text = (f"🔗 **Твоя ссылка для приглашений:**\n`{link}`\n\n"
                f"🎁 Дарим `0.50$` за каждого активного друга!")
        bot.send_message(m.chat.id, text, parse_mode="Markdown")

    elif m.text == "🏆 Топ Лидеров":
        top = supabase.table("users").select("first_name, refs_count").order("refs_count", desc=True).limit(5).execute().data
        text = "🔥 **ЛУЧШИЕ ПРИГЛАСИТЕЛИ:**\n\n"
        for i, user in enumerate(top, 1):
            text += f"{i}. {user['first_name']} — `{user['refs_count']}` приглашенных\n"
        bot.send_message(m.chat.id, text, parse_mode="Markdown")

    elif m.text == "💳 Вывод":
        u = get_user(uid)
        if float(u['balance']) < 5.0:
            bot.send_message(m.chat.id, f"❌ **Недостаточно средств.**\nМинимум: `5$`\nВаш баланс: `{u['balance']}$`", parse_mode="Markdown")
        else:
            user_state[uid] = 'wait_wallet'
            bot.send_message(m.chat.id, "⌨️ **Введите номер карты или крипто-кошелек:**", reply_markup=telebot.types.ReplyKeyboardRemove(), parse_mode="Markdown")

# --- WEBHOOK ---
@app.route('/', methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "ok", 200
