import os
import re
import tempfile
import time
from flask import Flask
from threading import Thread
from telegram import Update, InputFile
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    CallbackContext, ConversationHandler
)

app = Flask('')

@app.route('/')
def home():
    return "Bot is online!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# === CONFIG ===
TOKEN = "7210389776:AAEWbAsgCtWQ9GOPKqAhIo7HvzRYajPCqyg"
ADMIN_ID = 1485166650
ALLOWED_USERS_FILE = "allowed_users.txt"
GET_BASE_NAME, GET_FILE_NAME, GET_CONTACTS_PER_FILE = range(3)

def load_allowed_users():
    if os.path.exists(ALLOWED_USERS_FILE):
        with open(ALLOWED_USERS_FILE, "r") as f:
            return set(map(int, f.read().splitlines()))
    return {ADMIN_ID}

def save_allowed_users(users):
    with open(ALLOWED_USERS_FILE, "w") as f:
        f.write("\n".join(map(str, users)))

ALLOWED_USERS = load_allowed_users()

def is_allowed(user_id):
    return user_id in ALLOWED_USERS

def send_typing(action, update, context):
    context.bot.send_chat_action(chat_id=update.effective_chat.id, action=action)
    time.sleep(0.5)

def extract_base_and_number(name):
    match = re.search(r'^(.*?)(\d+)$', name)
    return (match.group(1), int(match.group(2))) if match else (name, 1)

def start(update: Update, context: CallbackContext):
    if not is_allowed(update.effective_user.id):
        send_typing("typing", update, context)
        update.message.reply_text("⛔ Access Denied! Contact admin")
        return
    send_typing("typing", update, context)
    update.message.reply_text(
        "✨ *Ultimate TXT-to-VCF Converter* ✨\n\n"
        "📁 Send your TXT file to begin\n"
        "⚡ Auto numbering: C1→C2, twitter11→twitter12",
        parse_mode="Markdown"
    )

def add_user(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("⛔ Only admin can use this command.")
        return
    if not context.args:
        update.message.reply_text("Usage: /adduser <user_id>")
        return
    try:
        user_id = int(context.args[0])
        ALLOWED_USERS.add(user_id)
        save_allowed_users(ALLOWED_USERS)
        update.message.reply_text(f"✅ User {user_id} added.")
    except:
        update.message.reply_text("❌ Invalid user ID.")

def remove_user(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("⛔ Only admin can use this command.")
        return
    if not context.args:
        update.message.reply_text("Usage: /removeuser <user_id>")
        return
    try:
        user_id = int(context.args[0])
        ALLOWED_USERS.discard(user_id)
        save_allowed_users(ALLOWED_USERS)
        update.message.reply_text(f"✅ User {user_id} removed.")
    except:
        update.message.reply_text("❌ Invalid user ID.")

def handle_file(update: Update, context: CallbackContext):
    if not is_allowed(update.effective_user.id):
        update.message.reply_text("🔒 Unauthorized!")
        return
    file = update.message.document
    if not file.file_name.lower().endswith('.txt'):
        update.message.reply_text("❌ Only TXT files accepted")
        return
    context.user_data['temp_file'] = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
    file.get_file().download(context.user_data['temp_file'].name)
    update.message.reply_text("🔤 Enter Base Name (e.g., twitter11):")
    return GET_BASE_NAME

def get_base_name(update: Update, context: CallbackContext):
    context.user_data['base_name'] = update.message.text
    update.message.reply_text("📝 Enter File Prefix (e.g., batch5):")
    return GET_FILE_NAME

def get_file_name(update: Update, context: CallbackContext):
    context.user_data['file_name'] = update.message.text
    update.message.reply_text("🔢 Contacts per File (e.g., 50):")
    return GET_CONTACTS_PER_FILE

def process_file(update: Update, context: CallbackContext):
    try:
        contacts_per_file = int(update.message.text)
        if contacts_per_file <= 0:
            raise ValueError
        msg = update.message.reply_text("⚙️ Processing... 0%")

        with open(context.user_data['temp_file'].name, 'r') as f:
            numbers = [re.sub(r'\D', '', line.strip()) for line in f if line.strip()]
        if not numbers:
            msg.edit_text("❌ No valid numbers found!")
            return ConversationHandler.END

        base_prefix, start_num = extract_base_and_number(context.user_data['base_name'])
        file_prefix, file_start_num = extract_base_and_number(context.user_data['file_name'])

        for i in range(0, len(numbers), contacts_per_file):
            batch = numbers[i:i + contacts_per_file]
            percent = int((i + len(batch)) / len(numbers) * 100)
            msg.edit_text(f"⚙️ Processing... {percent}%")

            with tempfile.NamedTemporaryFile(delete=False, suffix='.vcf') as vcf_file:
                for j, num in enumerate(batch):
                    contact_num = start_num + i + j
                    vcf_file.write(
                        f"BEGIN:VCARD\nVERSION:3.0\nFN:{base_prefix}{contact_num}\nTEL:{num}\nEND:VCARD\n".encode()
                    )
                vcf_file.flush()
                with open(vcf_file.name, 'rb') as f:
                    update.message.reply_document(
                        document=f,
                        filename=f"{file_prefix}{file_start_num + (i//contacts_per_file)}.vcf"
                    )
            os.unlink(vcf_file.name)

        msg.edit_text(f"🎉 Converted {len(numbers)} contacts!")
    except Exception as e:
        update.message.reply_text(f"❌ Error processing file: {e}")
    finally:
        if 'temp_file' in context.user_data:
            os.unlink(context.user_data['temp_file'].name)
    return ConversationHandler.END

def main():
    keep_alive()
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("adduser", add_user, pass_args=True))
    dp.add_handler(CommandHandler("removeuser", remove_user, pass_args=True))

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
    updater.idle()

if __name__ == '__main__':
    main()
