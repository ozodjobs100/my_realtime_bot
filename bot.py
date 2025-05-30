import os
import sqlite3
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.ext import JobQueue
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DB_FILE = "users.db"
LOG_FILE = "logs.txt"
BROADCAST_FILE = "message.txt"

# Initialize database
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Add user to database
def add_user(user):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
        VALUES (?, ?, ?, ?)
    ''', (user.id, user.username, user.first_name, user.last_name))
    conn.commit()
    conn.close()

# Get all user IDs and info
def get_all_users():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT user_id, username, first_name, last_name FROM users')
    users = c.fetchall()
    conn.close()
    return users

# Get all user IDs only
def get_all_user_ids():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT user_id FROM users')
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

# Log messages
def log_message(user, message):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now()}] {user.id} ({user.username}): {message}\n")

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user)
    keyboard = [
        [InlineKeyboardButton("📊 Statistika", callback_data="stats")],
        [InlineKeyboardButton("📝 Xabar yuborish", callback_data="send_message")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Botga xush kelibsiz!", reply_markup=reply_markup)

# Write command
async def write(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bu buyruq faqat admin uchun.")
        return
    if not context.args:
        await update.message.reply_text("❗ Xabar matnini yozing: /write Salom hammaga!")
        return
    message_text = " ".join(context.args)
    users = get_all_user_ids()
    count = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=f"One good person:\n{message_text}")
            count += 1
        except:
            pass
    await update.message.reply_text(f"✅ {count} ta foydalanuvchiga yuborildi.")

# Broadcast command
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bu buyruq faqat admin uchun.")
        return
    if not os.path.exists(BROADCAST_FILE):
        await update.message.reply_text("❗ message.txt topilmadi.")
        return
    with open(BROADCAST_FILE, "r", encoding="utf-8") as f:
        message_text = f.read().strip()
    if not message_text:
        await update.message.reply_text("❗ message.txt bo‘sh.")
        return
    users = get_all_user_ids()
    count = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=f"One good person:\n{message_text}")
            count += 1
        except:
            pass
    await update.message.reply_text(f"✅ Fayldan {count} ta foydalanuvchiga yuborildi.")

# Stats command
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bu buyruq faqat admin uchun.")
        return
    users = get_all_user_ids()
    await update.message.reply_text(f"👥 Foydalanuvchilar soni: {len(users)}")

# Set timer command
async def set_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bu buyruq faqat admin uchun.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("❗ Foydalanish: /set_timer <soniya> <xabar>")
        return
    try:
        delay = int(context.args[0])
        message_text = " ".join(context.args[1:])
        context.job_queue.run_once(
            callback=send_scheduled_message,
            when=delay,
            data=message_text,
            name=str(update.effective_user.id)
        )
        await update.message.reply_text(f"⏰ Xabar {delay} soniyadan so‘ng yuboriladi.")
    except ValueError:
        await update.message.reply_text("❗ Noto‘g‘ri format. Foydalanish: /set_timer <soniya> <xabar>")

# Send scheduled message
async def send_scheduled_message(context: ContextTypes.DEFAULT_TYPE):
    message_text = context.job.data
    users = get_all_user_ids()
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=f"⏰ Rejalashtirilgan xabar:\n{message_text}")
        except:
            pass

# Handle messages: add user, log, forward to admin
# Va reply qilingan userga xabar jo'natishni qo'shamiz
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user)
    log_message(user, update.message.text)

    # Agar admin reply qilsa va reply qilingan userga xabar jo'natish kerak bo'lsa:
    if update.message.reply_to_message and user.id == ADMIN_ID:
        replied_msg = update.message.reply_to_message
        # reply qilinayotgan xabar kimdan kelganligini aniqlaymiz
        original_sender_id = replied_msg.forward_from.id if replied_msg.forward_from else None
        
        # Agar forward qilingan xabar bo'lsa, forward_from orqali user_id olamiz
        if original_sender_id:
            try:
                await context.bot.send_message(chat_id=original_sender_id, text=update.message.text)
                await update.message.reply_text("✅ Xabar yuborildi.")
            except Exception as e:
                await update.message.reply_text(f"❌ Xabar yuborishda xato: {e}")
        else:
            await update.message.reply_text("❗ Bu xabarga javob berish orqali foydalanuvchiga xabar yuborishingiz mumkin.")
    else:
        # Oddiy foydalanuvchi xabarlarini adminga yuboramiz
        if user.id != ADMIN_ID:
            try:
                await context.bot.forward_message(chat_id=ADMIN_ID, from_chat_id=user.id, message_id=update.message.message_id)
            except:
                pass

# /users buyrug'i - barcha userlarni ko'rsatadi (admin uchun)
async def users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bu buyruq faqat admin uchun.")
        return

    users = get_all_users()
    if not users:
        await update.message.reply_text("Foydalanuvchilar topilmadi.")
        return

    message_text = "👥 Foydalanuvchilar ro'yxati:\n\n"
    lines = []
    for i, (user_id, username, first_name, last_name) in enumerate(users, start=1):
        username_str = f"@{username}" if username else "(username yo'q)"
        first_name_str = first_name if first_name else ""
        last_name_str = last_name if last_name else ""
        lines.append(f"{i}. ID: {user_id}\n   Username: {username_str}\n   Ismi: {first_name_str} {last_name_str}")

    full_text = message_text + "\n\n".join(lines)

    MAX_LEN = 4000
    if len(full_text) > MAX_LEN:
        chunks = [full_text[i:i+MAX_LEN] for i in range(0, len(full_text), MAX_LEN)]
        for chunk in chunks:
            await update.message.reply_text(chunk)
    else:
        await update.message.reply_text(full_text)

# Handle button callbacks
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "stats":
        users = get_all_user_ids()
        await query.edit_message_text(text=f"👥 Foydalanuvchilar soni: {len(users)}")
    elif query.data == "send_message":
        await query.edit_message_text(text="📝 Xabar yuborishingiz mumkin: ")

# Main function
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("write", write))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("set_timer", set_timer))
    app.add_handler(CommandHandler("users", users_list))  # <-- Yangi /users buyrug'i
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("✅ Bot ishga tushdi. CTRL+C bilan to‘xtatiladi.")
    app.run_polling()

if __name__ == '__main__':
    main()
