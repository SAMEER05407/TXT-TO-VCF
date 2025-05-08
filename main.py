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

# Flask setup
app = Flask('')

@app.route('/')
def home():
    return "Bot is online!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ===== CONFIGURATION =====
TOKEN = "7210389776:AAEWbAsgCtWQ9GOPKqAhIo7HvzRYajPCqyg"
ADMIN_ID = 1485166650
ALLOWED_USERS = {ADMIN_ID}

GET_BASE_NAME, GET_FILE_NAME, GET_CONTACTS_PER_FILE, MANUAL_ADD = range(4)

def send_typing(action, update, context):
    context.bot.send_chat_action(chat_id=update.effective_chat.id, action=action)
    time.sleep(0.5)

def extract_base_and_number(name):
    match = re.search(r'^(.*?)(\d+)$', name)
    return (match.group(1), int(match.group(2))) if match else (name, 1)

def is_allowed(user_id):
    return user_id in ALLOWED_USERS

def start(update: Update, context: CallbackContext):
    if not is_allowed(update.effective_user.id):
        send_typing("typing", update, context)
        update.message.reply_text("⛔ Access Denied! Contact admin")
        return

    send_typing("typing", update, context)
    update.message.reply_text(
        "✨ *Ultimate TXT-to-VCF Converter* ✨\n\n"
        "📁 Send your TXT file to begin\n"
        "⚡ Auto numbering: C1→C2, twitter11→twitter12\n"
        "\n\nUse /adduser or /removeuser to manage access\nUse /manual to manually add numbers\n",
        parse_mode="Markdown"
    )

def add_user(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("⛔ Only admin can add users!")
        return
    try:
        user_id = int(context.args[0])
        ALLOWED_USERS.add(user_id)
        update.message.reply_text(f"✅ User {user_id} added!")
    except:
        update.message.reply_text("❌ Usage: /adduser <user_id>")

def remove_user(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("⛔ Only admin can remove users!")
        return
    try:
        user_id = int(context.args[0])
        if user_id in ALLOWED_USERS:
            ALLOWED_USERS.remove(user_id)
            update.message.reply_text(f"✅ User {user_id} removed!")
        else:
            update.message.reply_text("❌ User not found")
    except:
        update.message.reply_text("❌ Usage: /removeuser <user_id>")

def manual_start(update: Update, context: CallbackContext):
    if not is_allowed(update.effective_user.id):
        update.message.reply_text("⛔ Not authorized")
        return ConversationHandler.END
    update.message.reply_text("🔤 Send phone numbers separated by comma or newline")
    return MANUAL_ADD

def manual_process(update: Update, context: CallbackContext):
    numbers = re.findall(r'\d+', update.message.text)
    if not numbers:
        update.message.reply_text("❌ No valid numbers found!")
        return ConversationHandler.END

    with tempfile.NamedTemporaryFile(delete=False, suffix='.vcf') as vcf_file:
        for i, num in enumerate(numbers, start=1):
            vcf_file.write(
                f"BEGIN:VCARD\nVERSION:3.0\nFN:Contact{i}\nTEL:{num}\nEND:VCARD\n".encode()
            )
        vcf_file.flush()
        with open(vcf_file.name, 'rb') as f:
            update.message.reply_document(
                document=f,
                filename="manual_contacts.vcf",
                caption=f"✅ {len(numbers)} contacts saved."
            )
    os.unlink(vcf_file.name)
    return ConversationHandler.END

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
            numbers = [re.sub(r'\D', '', line.strip()) for line in f if re.search(r'\d+', line)]

        if not numbers:
            msg.edit_text("❌ No valid numbers found!")
            return ConversationHandler.END

        base_prefix, start_num = extract_base_and_number(context.user_data['base_name'])
        file_prefix, file_start_num = extract_base_and_number(context.user_data['file_name'])

        for i in range(0, len(numbers), contacts_per_file):
            batch = numbers[i:i + contacts_per_file]
            current_percent = min(100, int((i + len(batch)) / len(numbers) * 100))
            try:
                msg.edit_text(f"⚙️ Processing... {current_percent}%")
            except:
                pass

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
                        filename=f"{file_prefix}{file_start_num + (i//contacts_per_file)}.vcf",
                        caption=f"✅ {len(batch)} contacts"
                    )
            os.unlink(vcf_file.name)

        msg.edit_text(f"🎉 Converted {len(numbers)} contacts!")

    except ValueError:
        update.message.reply_text("❌ Enter valid number > 0!")
        return GET_CONTACTS_PER_FILE
    finally:
        if 'temp_file' in context.user_data:
            os.unlink(context.user_data['temp_file'].name)
    return ConversationHandler.END

def main():
    keep_alive()
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    file_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.document, handle_file)],
        states={
            GET_BASE_NAME: [MessageHandler(Filters.text, get_base_name)],
            GET_FILE_NAME: [MessageHandler(Filters.text, get_file_name)],
            GET_CONTACTS_PER_FILE: [MessageHandler(Filters.text, process_file)]
        },
        fallbacks=[]
    )

    manual_conv = ConversationHandler(
        entry_points=[CommandHandler("manual", manual_start)],
        states={MANUAL_ADD: [MessageHandler(Filters.text, manual_process)]},
        fallbacks=[]
    )

    dp.add_handler(file_conv)
    dp.add_handler(manual_conv)
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("adduser", add_user))
    dp.add_handler(CommandHandler("removeuser", remove_user))

    updater.start_polling(drop_pending_updates=True)
    updater.idle()

if __name__ == '__main__':
    main()
