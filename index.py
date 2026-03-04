import os
import psycopg2
import telebot
from flask import Flask, request

TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

def get_db_connection():
    if not DB_URL:
        print("DATABASE_URL не настроен")
        return None
    try:
        # Прямое использование DB_URL, так как мы добавили sslmode в саму строку
        conn = psycopg2.connect(DB_URL)
        return conn
    except Exception as e:
        print(f"Ошибка подключения к БД: {e}")
        return None

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
            print("БД инициализирована успешно")
        except Exception as e:
            print(f"Ошибка инициализации БД: {e}")
        finally:
            conn.close()

# Инициализируем при запуске
init_db()

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    ref_id = None
    
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])
    
    if ref_id == user_id: 
        ref_id = None

    conn = get_db_connection()
    if not conn:
        bot.reply_to(message, "⚠️ Сервис временно недоступен (ошибка БД).")
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
                bot.reply_to(message, "✅ Вы успешно зарегистрированы!")
            else:
                bot.reply_to(message, "С возвращением! Вы уже зарегистрированы.")
    except Exception as e:
        print(f"Ошибка запроса: {e}")
        bot.reply_to(message, "Произошла ошибка при регистрации.")
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
    return "Статус: Бот работает", 200
