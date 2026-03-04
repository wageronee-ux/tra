import os
import psycopg2
import telebot
from flask import Flask, request

# Берем переменные прямо из твоего Vercel
TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")

bot = telebot.TeleBot(TOKEN, threaded=False) if TOKEN else None
app = Flask(__name__)

def get_db_connection():
    try:
        # Очищаем URL от параметров пулера (pgbouncer), если ты забыл их удалить в Vercel
        url = DB_URL.split("?")[0]
        
        # Подключаемся. SSL обязателен для Supabase.
        return psycopg2.connect(url, sslmode='require', connect_timeout=10)
    except Exception as e:
        print(f"Ошибка подключения: {e}")
        return None

# Создаем таблицу, если её нет
def init_db():
    conn = get_db_connection()
    if conn:
        try:
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
        finally:
            conn.close()

init_db()

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    
    # Реферальная логика
    ref_id = None
    parts = message.text.split()
    if len(parts) > 1 and parts[1].isdigit():
        ref_id = int(parts[1])
    if ref_id == user_id: ref_id = None

    conn = get_db_connection()
    if not conn:
        bot.reply_to(message, "Ошибка: не удалось связаться с базой данных.")
        return

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
            if cur.fetchone() is None:
                cur.execute(
                    "INSERT INTO users (user_id, username, first_name, referrer_id) VALUES (%s, %s, %s, %s)",
                    (user_id, message.from_user.username, message.from_user.first_name, ref_id)
                )
                if ref_id:
                    cur.execute("UPDATE users SET refs_count = refs_count + 1 WHERE user_id = %s", (ref_id,))
                conn.commit()
                bot.reply_to(message, "Регистрация прошла успешно!")
            else:
                bot.reply_to(message, "Вы уже зарегистрированы.")
    except Exception as e:
        bot.reply_to(message, f"Ошибка выполнения запроса: {e}")
    finally:
        conn.close()

@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403

@app.route('/')
def index():
    return "Бот работает", 200
