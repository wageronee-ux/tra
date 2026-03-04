import os
import psycopg2
import telebot
from flask import Flask, request

# 1. Инициализация бота и Flask
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")

# ФИКС: Очистка строки подключения от параметров, которые не понимает psycopg2
if DB_URL and "pgbouncer=true" in DB_URL:
    DB_URL = DB_URL.replace("?pgbouncer=true", "").replace("&pgbouncer=true", "")

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# 2. Функция инициализации базы данных
def init_db():
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                # Создаем таблицу, если её нет
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
        print("БАЗА ДАННЫХ: Таблицы проверены/созданы успешно.")
    except Exception as e:
        print(f"ОШИБКА БД при инициализации: {e}")

# Запускаем проверку БД при старте приложения
init_db()

# 3. Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Извлекаем ID реферера из команды /start (например, /start 12345)
    text_parts = message.text.split()
    referrer_id = None
    if len(text_parts) > 1 and text_parts[1].isdigit():
        referrer_id = int(text_parts[1])
        if referrer_id == user_id: # Нельзя пригласить самого себя
            referrer_id = None

    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                # Проверяем, есть ли пользователь
                cur.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
                if cur.fetchone() is None:
                    # Добавляем нового пользователя
                    cur.execute("""
                        INSERT INTO users (user_id, username, first_name, referrer_id)
                        VALUES (%s, %s, %s, %s)
                    """, (user_id, username, first_name, referrer_id))
                    
                    # Если есть реферер, обновляем ему счетчик
                    if referrer_id:
                        cur.execute("UPDATE users SET refs_count = refs_count + 1 WHERE user_id = %s", (referrer_id,))
                    
                    conn.commit()
                    bot.reply_to(message, f"Добро пожаловать, {first_name}! Вы зарегистрированы.")
                else:
                    bot.reply_to(message, "Вы уже зарегистрированы в системе.")
    except Exception as e:
        print(f"ОШИБКА при регистрации пользователя: {e}")
        bot.reply_to(message, "Произошла ошибка при работе с базой данных.")

# 4. Основной Webhook обработчик
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        try:
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            return "OK", 200
        except Exception as e:
            print(f"ОШИБКА обработки Update: {e}")
            # Возвращаем 200, чтобы Telegram не слал это проблемное сообщение вечно
            return "Error Handled", 200
    else:
        return "Invalid Request", 403

@app.route('/')
def index():
    return "Bot is running...", 200

# Для локального запуска
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
