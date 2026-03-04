import os
import psycopg2
import telebot
from flask import Flask, request

# 1. Инициализация переменных из твоего Vercel Dashboard
TOKEN = os.getenv("BOT_TOKEN")  # Проверь, что в Vercel имя именно такое
DB_URL = os.getenv("DATABASE_URL")

# Создаем объект бота с проверкой на наличие токена
if not TOKEN:
    print("КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не найден!")
    bot = None
else:
    bot = telebot.TeleBot(TOKEN, threaded=False)

app = Flask(__name__)

# 2. Функция безопасного подключения к БД
def get_db_connection():
    if not DB_URL:
        return None
    try:
        # Для работы с Vercel и Supabase (избегаем ошибки IPv6) 
        # используем строку подключения как есть, добавляя SSL
        conn_str = DB_URL
        if "sslmode=" not in conn_str:
            separator = "&" if "?" in conn_str else "?"
            conn_str += f"{separator}sslmode=require"
            
        return psycopg2.connect(conn_str, connect_timeout=10)
    except Exception as e:
        print(f"Ошибка подключения к БД: {e}")
        return None

# 3. Автоматическое создание таблицы при запуске функции
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
            print("Таблица проверена/создана успешно.")
        except Exception as e:
            print(f"Ошибка инициализации таблицы: {e}")
        finally:
            conn.close()

# Запускаем проверку базы данных
init_db()

# 4. Обработчик команды /start с реферальной системой
if bot:
    @bot.message_handler(commands=['start'])
    def start(message):
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name

        # Пытаемся достать ID реферера из ссылки
        ref_id = None
        args = message.text.split()
        if len(args) > 1 and args[1].isdigit():
            ref_id = int(args[1])
        
        # Нельзя пригласить самого себя
        if ref_id == user_id:
            ref_id = None

        conn = get_db_connection()
        if not conn:
            bot.reply_to(message, "⚠️ Ошибка базы данных. Попробуйте позже.")
            return

        try:
            with conn.cursor() as cur:
                # Проверяем, есть ли пользователь в базе
                cur.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
                if cur.fetchone() is None:
                    # Регистрация нового пользователя
                    cur.execute(
                        "INSERT INTO users (user_id, username, first_name, referrer_id) VALUES (%s, %s, %s, %s)",
                        (user_id, username, first_name, ref_id)
                    )
                    # Если есть пригласивший — обновляем его счетчик
                    if ref_id:
                        cur.execute("UPDATE users SET refs_count = refs_count + 1 WHERE user_id = %s", (ref_id,))
                    
                    conn.commit()
                    bot.reply_to(message, f"Привет, {first_name}! Ты успешно зарегистрирован.")
                else:
                    bot.reply_to(message, "Ты уже есть в нашей базе!")
        except Exception as e:
            bot.reply_to(message, f"Произошла ошибка: {str(e)}")
        finally:
            conn.close()

# 5. Обработка Webhook от Telegram
@app.route('/', methods=['POST'])
def webhook():
    if not bot:
        return "Bot misconfigured", 500
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403

@app.route('/')
def index():
    return "Бот активен и готов к работе!", 200
