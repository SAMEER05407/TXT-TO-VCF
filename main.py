import os
import re
import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Bot Configurations
TOKEN = "7210389776:AAEWbAsgCtWQ9GOPKqAhIo7HvzRYajPCqyg"
ADMIN_ID = 1485166650
ALLOWED_USERS_FILE = "allowed_users.txt"

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# States
ASK_BASENAME = 1
user_sessions = {}

# User Management
def load_allowed_users():
    if os.path.exists(ALLOWED_USERS_FILE):
        with open(ALLOWED_USERS_FILE, "r") as f:
            return set(map(int, f.read().splitlines()))
    return {ADMIN_ID}

def save_allowed_users(users):
    with open(ALLOWED_USERS_FILE, "w") as f:
        f.write("\n".join(map(str, users)))

ALLOWED_USERS = load_allowed_users()

# Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID and user_id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Access Denied! Contact admin.")
        return
    welcome = """
👋 *Welcome to TXT to VCF Converter Bot!*

📁 *Upload your .txt file* with numbers (one per line)
📝 *You will be asked to enter base name*
📤 The bot will send you clean VCF file(s)

✅ *Only valid numbers will be processed*
⚙️ Created with love by @yourusername
    """
    await update.message.reply_markdown(welcome)

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        user_id = int(context.args[0])
        ALLOWED_USERS.add(user_id)
        save_allowed_users(ALLOWED_USERS)
        await update.message.reply_text(f"✅ User {user_id} added!")
    except:
        await update.message.reply_text("❌ Usage: /adduser <user_id>")

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        user_id = int(context.args[0])
        ALLOWED_USERS.discard(user_id)
        save_allowed_users(ALLOWED_USERS)
        await update.message.reply_text(f"✅ User {user_id} removed!")
    except:
        await update.message.reply_text("❌ Usage: /removeuser <user_id>")

# File Handling
async def handle_txt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID and user_id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Access Denied!")
        return
    doc = update.message.document
    if doc.mime_type != "text/plain":
        await update.message.reply_text("❌ Please send a .txt file only.")
        return
    file = await doc.get_file()
    file_path = f"{user_id}.txt"
    await file.download_to_drive(file_path)
    user_sessions[user_id] = file_path
    await update.message.reply_text("🔤 Enter Base Name (e.g., TwitterContacts):")
    return ASK_BASENAME

async def convert_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    base_name = update.message.text.strip()
    txt_path = user_sessions.get(user_id)
    if not txt_path:
        await update.message.reply_text("❌ No TXT file found. Please send a .txt file first.")
        return ConversationHandler.END

    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

        numbers = [re.sub(r'\D', '', line) for line in lines if re.sub(r'\D', '', line)]
        chunk_size = 1000
        total = len(numbers)
        await update.message.reply_text(f"✅ Found {total} valid numbers. Creating VCF...")

        for i in range(0, total, chunk_size):
            chunk = numbers[i:i+chunk_size]
            vcf_data = ""
            for idx, number in enumerate(chunk):
                vcf_data += f"BEGIN:VCARD\nVERSION:3.0\nFN:{base_name} {i + idx + 1}\nTEL;TYPE=CELL:{number}\nEND:VCARD\n"
            filename = f"{base_name}_{(i // chunk_size) + 1}.vcf"
            with open(filename, "w") as vcf_file:
                vcf_file.write(vcf_data)
            await update.message.reply_document(document=open(filename, "rb"))
            os.remove(filename)

        os.remove(txt_path)
        user_sessions.pop(user_id, None)
    except Exception as e:
        await update.message.reply_text(f"❌ Error processing file: {e}")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operation cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# Main App
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Document.MIME_TYPE("text/plain"), handle_txt)],
        states={ASK_BASENAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, convert_and_send)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("adduser", add_user))
    app.add_handler(CommandHandler("removeuser", remove_user))
    app.add_handler(conv_handler)

    print("Bot running...")
    app.run_polling()
