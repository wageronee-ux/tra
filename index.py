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

# --- КЛАВИАТУРА ---
def main_kb():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🏆 Топ лидеров")
    markup.add("🔗 Реф. ссылка", "💸 Вывод средств")
    return markup

def sub_kb():
    # Для подписки используем инлайн (так как нужна ссылка), 
    # но основное управление будет в Reply.
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_LINK))
    return kb

# --- ПРОВЕРКА ПОДПИСКИ ---
def is_sub(uid):
    try:
        s = bot.get_chat_member(CHANNEL_ID, uid).status
        return s in ['member', 'administrator', 'creator']
    except: return False

@bot.message_handler(commands=['start'])
def start(m):
    uid = str(m.from_user.id)
    if not is_sub(uid):
        return bot.send_message(m.chat.id, "👋 **Привет!**\n\nДля работы с ботом подпишись на наш канал:", 
                                reply_markup=sub_kb(), parse_mode="Markdown")

    # Регистрация
    user = supabase.table("users").select("user_id").eq("user_id", uid).execute().data
    if not user:
        ref_id = m.text.split()[1] if len(m.text.split()) > 1 else None
        supabase.table("users").insert({
            "user_id": uid, "first_name": m.from_user.first_name,
            "referrer_id": ref_id, "balance": 0, "refs_count": 0
        }).execute()
        
        if ref_id and ref_id != uid:
            # Начисление (упрощенное)
            r_data = supabase.table("users").select("balance, refs_count").eq("user_id", ref_id).execute().data
            if r_data:
                supabase.table("users").update({
                    "balance": float(r_data[0]['balance']) + 0.50,
                    "refs_count": int(r_data[0]['refs_count']) + 1
                }).eq("user_id", ref_id).execute()
                try: bot.send_message(ref_id, "🎁 **У вас новый реферал!** +0.50$", parse_mode="Markdown")
                except: pass

    bot.send_message(m.chat.id, "🎯 **Вы в главном меню.**\nИспользуйте кнопки ниже:", reply_markup=main_kb(), parse_mode="Markdown")

# --- ОБРАБОТКА ТЕКСТОВЫХ КОМАНД ---
@bot.message_handler(content_types=['text'])
def handle_text(m):
    uid = str(m.from_user.id)
    
    # Сначала проверяем, не ждем ли мы кошелек
    if user_state.get(uid) == 'wait_w':
        amount = supabase.table("users").select("balance").eq("user_id", uid).single().execute().data['balance']
        supabase.table("users").update({"balance": 0}).eq("user_id", uid).execute()
        bot.send_message(ADMIN_ID, f"💰 **ЗАЯВКА**\nID: `{uid}`\nСумма: `{amount}$`\nРеквизиты: `{m.text}`", parse_mode="Markdown")
        user_state[uid] = None
        return bot.send_message(m.chat.id, "✅ **Заявка принята!**\nОжидайте выплату в течение суток.", reply_markup=main_kb(), parse_mode="Markdown")

    if not is_sub(uid):
        return bot.send_message(m.chat.id, "❗ Сначала подпишись на канал!", reply_markup=sub_kb())

    if m.text == "👤 Профиль":
        u = supabase.table("users").select("*").eq("user_id", uid).single().execute().data
        msg = (f"─── **ВАШ ПРОФИЛЬ** ───\n\n"
               f"👤 Имя: `{u['first_name']}`\n"
               f"💰 Баланс: `{u['balance']}$`\n"
               f"👥 Рефералов: `{u['refs_count']}`\n"
               f"──────────────────")
        bot.send_message(m.chat.id, msg, parse_mode="Markdown")

    elif m.text == "🔗 Реф. ссылка":
        bot_user = bot.get_me().username
        link = f"https://t.me/{bot_user}?start={uid}"
        bot.send_message(m.chat.id, f"📢 **Приглашай друзей и зарабатывай!**\n\nЗа каждого друга ты получишь `0.50$`\n\nТвоя ссылка:\n`{link}`", parse_mode="Markdown")

    elif m.text == "🏆 Топ лидеров":
        top = supabase.table("users").select("first_name, refs_count").order("refs_count", desc=True).limit(10).execute().data
        txt = "🏆 **ТОП-10 ПРИГЛАСИТЕЛЕЙ**\n\n"
        for i, user in enumerate(top, 1):
            txt += f"{i}. {user['first_name']} — `{user['refs_count']}` чел.\n"
        bot.send_message(m.chat.id, txt, parse_mode="Markdown")

    elif m.text == "💸 Вывод средств":
        u = supabase.table("users").select("balance").eq("user_id", uid).single().execute().data
        if float(u['balance']) < 5:
            bot.send_message(m.chat.id, f"❌ **Недостаточно средств!**\n\nМинимальный вывод: `5$`\nВаш баланс: `{u['balance']}$`", parse_mode="Markdown")
        else:
            user_state[uid] = 'wait_w'
            bot.send_message(m.chat.id, "💳 **Введите реквизиты**\n(Карта или адрес кошелька):", 
                             reply_markup=telebot.types.ReplyKeyboardRemove(), parse_mode="Markdown")

# --- WEBHOOK ---
@app.route('/', methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "ok", 200
