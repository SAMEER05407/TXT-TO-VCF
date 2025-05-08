import os
import re
import tempfile
import time
from flask import Flask
from threading import Thread
from telegram import Update, InputFile
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    ConversationHandler
)

# === Web server to keep bot alive ===
app = Flask('')
@app.route('/')
def home():
    return "Bot is online!"
def run():
    app.run(host='0.0.0.0', port=8080)
def keep_alive():
    Thread(target=run).start()

# === Bot Configuration ===
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

def send_typing(action, update, context):
    context.bot.send_chat_action(chat_id=update.effective_chat.id, action=action)
    time.sleep(0.5)

def extract_base_and_number(name):
    match = re.search(r'^(.*?)(\d+)$', name)
    return (match.group(1), int(match.group(2))) if match else (name, 1)

def start(update: Update, context: CallbackContext):
    if not is_allowed(update.effective_user.id):
        send_typing("typing", update, context)
        update.message.reply_text("⛔ Access Denied! Contact admin.")
        return
    update.message.reply_text("Welcome! Send a .txt file to start converting.")

def handle_file(update: Update, context: CallbackContext):
    if not is_allowed(update.effective_user.id):
        update.message.reply_text("⛔ Access Denied.")
        return
    file = update.message.document
    if not file.file_name.lower().endswith(".txt"):
        update.message.reply_text("❌ Please upload a .txt file.")
        return
    context.user_data["temp_file"] = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    file.get_file().download(custom_path=context.user_data["temp_file"].name)
    update.message.reply_text("🔤 Enter Base Name (e.g. twitter11):")
    return GET_BASE_NAME

def get_base_name(update: Update, context: CallbackContext):
    context.user_data["base_name"] = update.message.text
    update.message.reply_text("📝 Enter File Prefix (e.g. batch1):")
    return GET_FILE_NAME

def get_file_name(update: Update, context: CallbackContext):
    context.user_data["file_name"] = update.message.text
    update.message.reply_text("🔢 Contacts per file (e.g. 50):")
    return GET_CONTACTS_PER_FILE

def process_file(update: Update, context: CallbackContext):
    try:
        count = int(update.message.text)
        if count <= 0:
            raise ValueError("Invalid count.")
        msg = update.message.reply_text("⚙️ Processing... 0%")
        with open(context.user_data["temp_file"].name, "r") as f:
            lines = f.readlines()
        numbers = [line.strip() for line in lines if line.strip().isdigit()]
        if not numbers:
            msg.edit_text("❌ No valid numbers found!")
            return ConversationHandler.END

        base_prefix, start_num = extract_base_and_number(context.user_data["base_name"])
        file_prefix, file_start = extract_base_and_number(context.user_data["file_name"])
        total = len(numbers)
        for i in range(0, total, count):
            batch = numbers[i:i+count]
            percent = int(((i+count)/total)*100)
            try:
                msg.edit_text(f"⚙️ Processing... {min(percent, 100)}%")
            except: pass
            with tempfile.NamedTemporaryFile(delete=False, suffix=".vcf") as vcf_file:
                for j, num in enumerate(batch):
                    contact_num = start_num + i + j
                    vcf_file.write(
                        f"BEGIN:VCARD\nVERSION:3.0\nFN:{base_prefix}{contact_num}\nTEL:{num}\nEND:VCARD\n".encode()
                    )
                vcf_file.flush()
                with open(vcf_file.name, "rb") as f:
                    update.message.reply_document(
                        document=f,
                        filename=f"{file_prefix}{file_start + (i//count)}.vcf",
                        caption=f"✅ {len(batch)} contacts done."
                    )
            os.unlink(vcf_file.name)
        msg.edit_text("🎉 Done! All VCFs sent.")
    except:
        update.message.reply_text("❌ Error processing file.")
    finally:
        if "temp_file" in context.user_data:
            os.unlink(context.user_data["temp_file"].name)
    return ConversationHandler.END

def add_user(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return update.message.reply_text("⛔ Only admin can use this command.")
    try:
        uid = int(context.args[0])
        ALLOWED_USERS.add(uid)
        save_allowed_users(ALLOWED_USERS)
        update.message.reply_text(f"✅ User {uid} added.")
    except:
        update.message.reply_text("❌ Invalid user ID.")

def remove_user(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return update.message.reply_text("⛔ Only admin can use this command.")
    try:
        uid = int(context.args[0])
        ALLOWED_USERS.discard(uid)
        save_allowed_users(ALLOWED_USERS)
        update.message.reply_text(f"✅ User {uid} removed.")
    except:
        update.message.reply_text("❌ Invalid user ID.")

def main():
    keep_alive()
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("adduser", add_user))
    dp.add_handler(CommandHandler("removeuser", remove_user))
    file_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.document, handle_file)],
        states={
            GET_BASE_NAME: [MessageHandler(Filters.text, get_base_name)],
            GET_FILE_NAME: [MessageHandler(Filters.text, get_file_name)],
            GET_CONTACTS_PER_FILE: [MessageHandler(Filters.text, process_file)],
        },
        fallbacks=[]
    )
    dp.add_handler(file_handler)
    updater.start_polling()
    print("✅ Bot is running.")
    updater.idle()

if __name__ == "__main__":
    main()
