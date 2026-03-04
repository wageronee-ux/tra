import os
import psycopg2
import telebot
from flask import Flask, request

# 1. Инициализация (Имена изменены под твои скриншоты в Vercel)
TOKEN = os.getenv("BOT_TOKEN")  # Было TELEGRAM_BOT_TOKEN
DB_URL = os.getenv("DATABASE_URL")

# Проверка токена (чтобы бот не падал с непонятной ошибкой)
if not TOKEN:
    print("CRITICAL ERROR: BOT_TOKEN is not found in Environment Variables!")
    # Создаем заглушку, чтобы Flask запустился и выдал ошибку в логи, а не просто упал
    bot = None
else:
    bot = telebot.TeleBot(TOKEN, threaded=False)

app = Flask(__name__)

# 2. Очистка URL базы данных
if DB_URL and "pgbouncer=true" in DB_URL:
    DB_URL = DB_URL.replace("?pgbouncer=true", "").replace("&pgbouncer=true", "")

def init_db():
    if not DB_URL:
        print("DATABASE_URL is missing!")
        return
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        referrer_id BIGINT,
                        refs_count INTEGER DEFAULT 0
                    );
                """)
                conn.commit()
    except Exception as e:
        print(f"DB Init Error: {e}")

init_db()

# 3. Обработчики (только если бот инициализирован)
if bot:
    @bot.message_handler(commands=['start'])
    def start(message):
        user_id = message.from_user.id
        # Извлекаем ID реферера
        text_parts = message.text.split()
        referrer_id = int(text_parts[1]) if len(text_parts) > 1 and text_parts[1].isdigit() else None
        if referrer_id == user_id: referrer_id = None

        try:
            with psycopg2.connect(DB_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
                    if cur.fetchone() is None:
                        cur.execute("INSERT INTO users (user_id, username, first_name, referrer_id) VALUES (%s, %s, %s, %s)",
                                    (user_id, message.from_user.username, message.from_user.first_name, referrer_id))
                        if referrer_id:
                            cur.execute("UPDATE users SET refs_count = refs_count + 1 WHERE user_id = %s", (referrer_id,))
                        conn.commit()
                        bot.reply_to(message, "Регистрация прошла успешно!")
                    else:
                        bot.reply_to(message, "Вы уже в системе.")
        except Exception as e:
            bot.reply_to(message, "Ошибка базы данных.")

# 4. Webhook
@app.route('/', methods=['POST'])
def webhook():
    if not bot:
        return "Bot token missing", 500
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403

@app.route('/')
def index():
    return "Bot is active" if bot else "Bot is misconfigured (check token)", 200
