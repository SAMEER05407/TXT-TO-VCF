# START of main.py
import os
import re
import tempfile
import time
import logging
from flask import Flask
from threading import Thread
from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

# Enable logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask('')
@app.route('/')
def home():
    return "Bot is online!"
def run():
    app.run(host='0.0.0.0', port=8080)
def keep_alive():
    Thread(target=run).start()

# === Bot Config ===
TOKEN = "7210389776:AAEWbAsgCtWQ9GOPKqAhIo7HvzRYajPCqyg"
ADMIN_ID = 1485166650
ALLOWED_USERS_FILE = "allowed_users.txt"
GET_BASE_NAME, GET_FILE_NAME, GET_CONTACTS_PER_FILE = range(3)

def load_allowed_users():
    if os.path.exists(ALLOWED_USERS_FILE):
        with open(ALLOWED_USERS_FILE, "r") as f:
            return set(map(int, f.read().splitlines()))
    return set()

def save_allowed_users(users):
    with open(ALLOWED_USERS_FILE, "w") as f:
        f.write("\n".join(map(str, users)))

ALLOWED_USERS = load_allowed_users()

def is_allowed(user_id):
    return user_id == ADMIN_ID or user_id in ALLOWED_USERS

# === Start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        await update.message.reply_text("⛔ Access Denied! Contact admin.")
        return
    await update.message.reply_text("Welcome! Send a .txt file to start converting.")

# === File Upload ===
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        await update.message.reply_text("⛔ Access Denied.")
        return ConversationHandler.END

    file = update.message.document
    if not file.file_name.lower().endswith(".txt"):
        await update.message.reply_text("❌ Please upload a .txt file.")
        return ConversationHandler.END

    file_path = tempfile.NamedTemporaryFile(delete=False, suffix=".txt").name
    await file.get_file().download_to_drive(file_path)
    context.user_data["temp_file"] = file_path
    await update.message.reply_text("🔤 Enter Base Name (e.g., twitter11):")
    return GET_BASE_NAME

async def get_base_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["base_name"] = update.message.text.strip()
    await update.message.reply_text("📝 Enter File Prefix (e.g., batch1):")
    return GET_FILE_NAME

async def get_file_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["file_name"] = update.message.text.strip()
    await update.message.reply_text("🔢 Contacts per file (e.g., 50):")
    return GET_CONTACTS_PER_FILE

def extract_base_and_number(name):
    match = re.search(r'^(.*?)(\d+)$', name)
    return (match.group(1), int(match.group(2))) if match else (name, 1)

async def process_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text.strip())
        if count <= 0:
            raise ValueError("Invalid number.")

        msg = await update.message.reply_text("⚙️ Processing...")

        with open(context.user_data["temp_file"], "r") as f:
            lines = f.readlines()

        numbers = [line.strip() for line in lines if line.strip().isdigit()]
        if not numbers:
            await msg.edit_text("❌ No valid numbers found!")
            return ConversationHandler.END

        base_prefix, start_num = extract_base_and_number(context.user_data["base_name"])
        file_prefix, file_start = extract_base_and_number(context.user_data["file_name"])
        total = len(numbers)

        for i in range(0, total, count):
            batch = numbers[i:i+count]
            with tempfile.NamedTemporaryFile(delete=False, suffix=".vcf") as vcf_file:
                for j, num in enumerate(batch):
                    contact_num = start_num + i + j
                    vcf_file.write(
                        f"BEGIN:VCARD\nVERSION:3.0\nFN:{base_prefix}{contact_num}\nTEL:{num}\nEND:VCARD\n".encode()
                    )
                vcf_file.flush()
                await update.message.reply_document(
                    document=InputFile(vcf_file.name),
                    filename=f"{file_prefix}{file_start + (i//count)}.vcf",
                    caption=f"✅ {len(batch)} contacts"
                )
                os.unlink(vcf_file.name)

        await msg.edit_text("✅ All VCF files sent!")
    except Exception as e:
        logger.error("Processing error: %s", e)
        await update.message.reply_text("❌ Error processing file.")
    finally:
        if "temp_file" in context.user_data:
            os.unlink(context.user_data["temp_file"])
    return ConversationHandler.END

# === Admin ===
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Only admin can use this command.")
    try:
        uid = int(context.args[0])
        ALLOWED_USERS.add(uid)
        save_allowed_users(ALLOWED_USERS)
        await update.message.reply_text(f"✅ User {uid} added.")
    except:
        await update.message.reply_text("❌ Invalid ID.")

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Only admin can use this command.")
    try:
        uid = int(context.args[0])
        ALLOWED_USERS.discard(uid)
        save_allowed_users(ALLOWED_USERS)
        await update.message.reply_text(f"✅ User {uid} removed.")
    except:
        await update.message.reply_text("❌ Invalid ID.")

# === Main ===
async def main():
    keep_alive()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("adduser", add_user))
    app.add_handler(CommandHandler("removeuser", remove_user))

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Document.ALL, handle_file)],
        states={
            GET_BASE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_base_name)],
            GET_FILE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_file_name)],
            GET_CONTACTS_PER_FILE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_file)],
        },
        fallbacks=[],
    )
    app.add_handler(conv_handler)

    print("✅ Bot is running.")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
# END of main.py
