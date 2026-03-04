import os
import psycopg2
import telebot
from flask import Flask, request

# 1. Настройка переменных (имена как в твоем Vercel)
TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")

# Проверка наличия токена, чтобы бот не падал с ошибкой итерации
if not TOKEN:
    print("Ошибка: BOT_TOKEN не найден в Environment Variables!")
    bot = None
else:
    bot = telebot.TeleBot(TOKEN, threaded=False)

app = Flask(__name__)

# 2. Функция для очистки и исправления URL базы данных
def get_db_connection():
    if not DB_URL:
        return None
    
    # Исправляем протокол postgres:// на postgresql:// для psycopg2
    temp_url = DB_URL
    if temp_url.startswith("postgres://"):
        temp_url = temp_url.replace("postgres://", "postgresql://", 1)
    
    # Убираем параметры pgbouncer, если они есть (они мешают прямому подключению)
    clean_url = temp_url.split("?")[0]
    
    # Подключаемся с SSL (часто требуется для внешних баз типа Supabase/Render)
    return psycopg2.connect(clean_url, sslmode='require')

# 3. Создание таблицы при запуске
def init_db():
    conn = None
    try:
        conn = get_db_connection()
        if conn:
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
                print("База данных готова.")
    except Exception as e:
        print(f"Ошибка инициализации БД: {e}")
    finally:
        if conn: conn.close()

init_db()

# 4. Обработка команды /start
if bot:
    @bot.message_handler(commands=['start'])
    def start(message):
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name
        
        # Получаем ID пригласившего из ссылки (если есть)
        text_parts = message.text.split()
        referrer_id = None
        if len(text_parts) > 1 and text_parts[1].isdigit():
            referrer_id = int(text_parts[1])
        
        # Защита: нельзя пригласить самого себя
        if referrer_id == user_id:
            referrer_id = None

        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                # Проверяем, есть ли юзер
                cur.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
                if cur.fetchone() is None:
                    # Регистрация нового
                    cur.execute(
                        "INSERT INTO users (user_id, username, first_name, referrer_id) VALUES (%s, %s, %s, %s)",
                        (user_id, username, first_name, referrer_id)
                    )
                    # Если есть реферер, прибавляем ему счетчик
                    if referrer_id:
                        cur.execute("UPDATE users SET refs_count = refs_count + 1 WHERE user_id = %s", (referrer_id,))
                    
                    conn.commit()
                    bot.reply_to(message, f"Добро пожаловать, {first_name}! Вы зарегистрированы.")
                else:
                    bot.reply_to(message, "Вы уже зарегистрированы в системе.")
        except Exception as e:
            bot.reply_to(message, f"Ошибка базы данных: {str(e)}")
        finally:
            if conn: conn.close()

# 5. Маршруты для Vercel (Webhook)
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
    status = "работает" if bot else "не настроен (проверь токен)"
    return f"Бот {status}", 200
